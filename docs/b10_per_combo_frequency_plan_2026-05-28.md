# B10 Per-Combo Frequency Feature Plan (W2.2 Unblock)

**Date:** 2026-05-28
**Status:** Plan (does not implement). 4-PR sequence.
**Predecessor spec:** `docs/pr_proposals/v1_range_fractional_frequency_spec.md` (2026-05-25). This plan ratifies the spec's 4-PR sequence with a W2.2-Sarah-first acceptance lens.

## 1. Why

`Range` currently stores combos at class-level (e.g. `"AKs"` → 4 combos all at implicit weight 1.0). GTO mixed strategies routinely call for within-class variation:

- **Suit blockers.** AsKs on a heart-flush board has different equity than AhKh. A GTO solver outputs `AsKs: 3-bet 70%, AhKh: 3-bet 30%`.
- **W2.2 Sarah literal-spec exemplar.** "KQo: you 3-bet 0%, GTO 25%." Today we cannot represent the 25%.

`RangeWithFreqs` in `ui/state.py:254-326` is a UI-layer wrapper that already adds per-combo `frequencies: dict[Combo, float]`. The refactor moves that capability into `Range` itself.

## 2. Phase A — Core data model + parser + serializer (~250 LOC, 1.5 days)

Files: `poker_solver/range.py`, `poker_solver/__init__.py`, `tests/test_range_frac_freq.py` (NEW).

### A.1 Promote `Combo` to a frozen dataclass

```python
@dataclass(frozen=True)
class Combo:
    cards: tuple[Card, Card]
    weight: float = 1.0  # NOT in __hash__ / __eq__

    def __iter__(self):  return iter(self.cards)
    def __getitem__(self, i):  return self.cards[i]
```

### A.2 Extend `Range` with weight storage

```python
@dataclass
class Range:
    combos: list[Combo] = field(default_factory=list)
    _combo_set: set[tuple[Card, Card]] = field(default_factory=set, repr=False)
    _weight: dict[tuple[Card, Card], float] = field(default_factory=dict, repr=False)
```

### A.3 New API surface

- `weight(combo) -> float`
- `set_weight(combo, w)` — raises on `w not in [0, 1]`
- `normalize() -> Range`
- `merge(other, mode='sum'|'max'|'union')`
- Extended `parse_range(spec)`: `"AKo:0.25, AA, KK:0.5, AhKh:0.3"`
- `to_string()` round-trip: all-1.0 unadorned; non-1.0 emit `:w`
- `add(combo, weight=1.0)` — duplicates sum, cap at 1.0
- `diff(other)` — frequency-aware: `w_out = max(self.w - other.w, 0)`
- `sample_excluding(excluded, rng)` — weighted; uniform fast-path when all weights == 1

## 3. Phase B — Aggregator + solver wiring (~200 LOC, 1.0 day)

Files: `poker_solver/range_aggregator.py`, `poker_solver/equity.py`, `crates/cfr_core/src/dcfr_vector.rs` (header docs only).

### B.1 Aggregator propagation

```python
def _aggregate_range(per_class, class_order, range_):
    for cls in class_order:
        # OLD: weight = float(_combo_count(cls))
        weight = sum(range_.weight(c) for c in _enumerate_combos(cls))
```

### B.2 Rust binding contract

`crates/cfr_core/src/dcfr_vector.rs` extends `p0_holes` / `p1_holes` to accept aligned `p0_weights` / `p1_weights` (`Vec<f64>`, default ones). Per-cell contribution becomes `weight[i] * hand_count[i]`. Multiplicative factor only — no algorithmic change.

### B.3 Differential tests

Add mixed-strategy case to `tests/test_range_vs_range_nash.py`: known-analytical Nash on a Kuhn-sized game; expect convergence within `5e-2`.

## 4. Phase C — GUI per-combo intensity editor (~150 LOC, 1.0 day)

Files: `ui/state.py`, `ui/views/range_matrix.py`, `ui/views/range_freq_editor.py` (verify only).

### C.1 `RangeWithFreqs` delegation

`frequencies` dict REMOVED — canonical store moves into `Range._weight`. Session migration: one-shot load-time upgrade walks the dict, calls `range.set_weight`. Strip on next save.

### C.2 Matrix saturation

Cell with avg weight 0.3 renders at ~30% color intensity. All-1.0 ranges render at full saturation (back-compat).

## 5. Phase D — CLI + W2.2 persona fixture (~80 LOC, 0.5 day)

CLI comes for free (already calls `parse_range` opaquely). Update help text. Append section to `docs/persona_test_results/W2_2_*_retest.md` with literal exemplar:

```python
gto = parse_range("KQo:0.25, ...")
user = parse_range("AA, KK, QQ, AKs, AKo")
gto.diff(user)  # returns Range with KQo at 0.25 — the previously inexpressible spec
```

Move W2.2 verdict PARTIAL → PASS.

## 6. Total estimate

| Phase | LOC | Days |
|---|---|---|
| A — Core | ~250 | 1.5 |
| B — Engine | ~200 | 1.0 |
| C — GUI | ~150 | 1.0 |
| D — Persona | ~80 | 0.5 |
| **Total** | **~680** | **~4** |

## 7. Backward-compat risk register

| Risk | Severity | Mitigation |
|---|---|---|
| `Combo` identity change | HIGH | Keep `_combo_set` keyed on `tuple[Card, Card]`; back-compat shims `__iter__`/`__getitem__`; explicit test `test_combo_hash_ignores_weight` |
| `RangeWithFreqs.frequencies` dict removal | HIGH | One-shot load-time session upgrade; strip on next save |
| `parse_range` `:weight` grammar collision | MEDIUM | Validate `:` not parseable in any prior token; clear `ValueError` on malformed |
| Rust binding `weight_list` parameter | MEDIUM | Default `Vec<f64>` of ones when absent |
| Library charts JSON round-trip | LOW | No fractional entries today; verify identical emit |
| Differential test regression | LOW | Existing all-1.0 diffs catch general regressions |

## 8. Test plan — suit-blocker closed-form

**Setup:** AsKs vs villain range on hearts-flush board (`Th 8h 4h`). AhKh blocks villain's nut flush; AsKs doesn't. GTO solver outputs `AsKs: 3-bet ~70%, AhKh: 3-bet ~30%`.

**Assertions:**
1. `solve_range_vs_range_nash(...)` with fractional ranges returns per-(combo, action) rows.
2. Projection aggregates AsKs and AhKh into AKs at weight-averaged frequency.
3. Within-class variation detectable in `per_history_strategy` (AsKs row != AhKh row).

## 9. PR landing sequence

Strict: A → B → C → D. Each PR's CI must be green before the next ships. No feature flag; back-compat invariant by construction.

| PR | Branch | Gates next? |
|---|---|---|
| (A) Core | `feat/range-frac-freq-core` | YES |
| (B) Engine | `feat/range-frac-freq-engine` | YES |
| (C) GUI | `feat/range-frac-freq-ui` | YES |
| (D) Persona | `test/range-frac-freq-w2-2` | NO (final) |

## 10. References

- Predecessor spec: `docs/pr_proposals/v1_range_fractional_frequency_spec.md`
- Master plan §B10: `docs/master_plan_remaining_2026-05-27.md`
- Aggregator framing: `docs/aggregator_vs_true_nash_explainer.md`
- W2.2 persona test: `docs/persona_test_results/W2_2_v1_4_1_retest.md`
