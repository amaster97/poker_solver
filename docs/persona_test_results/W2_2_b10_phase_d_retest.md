# W2.2 — Sarah `Range.diff` per-combo retest (B10 Phase D)

**Date:** 2026-05-28
**Tester:** automated agent (B10 Phase D persona verification)
**Persona / workflow:** Sarah — diffs her own user range against a GTO
solution and expects the leak surface to expose **per-combo frequency
deltas**, not just set-membership differences.
**Spec source / exemplar:** `docs/b10_per_combo_frequency_plan_2026-05-28.md`
§1 — "KQo: you 3-bet 0%, GTO 25%."
**Prior verdict:** **PARTIAL** (set-membership `Range.diff` only — see
`docs/persona_status_2026-05-28-late.md` §W2.2).
**Drivers:**

- `tests/test_w2_2_per_combo_diff.py` (4 tests, all PASS in ~30 ms)
- `scripts_retest/w2_2_per_combo_diff_retest.py` (human-readable fixture)

---

## Verdict

**PARTIAL → PASS.**

`Range.diff` is now frequency-aware end-to-end. The literal Sarah exemplar
("KQo: you 3-bet 0%, GTO 25%") that was previously inexpressible now
round-trips through the public `parse_range` / `Range.diff` API and
surfaces all 12 KQo combos at weight 0.25 — exactly the leak Sarah was
looking for.

**B10 phase trail:**

| Phase | PR | Subject |
|---|---|---|
| A | **#149** (`40ac87a`) | per-combo fractional weights core (`Combo` subclass, `Range._weight`, `parse_range` `:weight` grammar, `Range.diff` frequency-aware) |
| B | **#154** (`11e3f01`) | aggregator + solver weight propagation (`_aggregate_range`, `_project_to_hand_classes`, Rust `p0_weights`/`p1_weights` kwargs) |
| C | **#158** (`1839ee1`) | UI per-combo intensity editor |
| **D** | **this PR** | persona retest — fixture + test + verdict reclassification |

---

## Fixture results

All three cases run in well under 1 ms each on `.venv/bin/python` 3.13 arm64.

### Case 1 — literal exemplar

```python
gto  = parse_range("KQo:0.25")
user = parse_range("AA, KK, QQ, AKs, AKo")
diff = gto.diff(user)
```

| Field | Value |
|---|---|
| `len(diff)` | **12** (all KQo offsuit combos) |
| Distinct weights surfaced | `[0.25]` |
| `diff.to_string()` (head) | `"KsQh:0.25, KsQd:0.25, KsQc:0.25, KhQs:0.25, ..."` |
| Wall | ~0.15 ms |

The 25% that was previously inexpressible now appears in the diff. **This
is the W2.2 unblock.**

### Case 2 — per-combo partial subtraction

```python
a = parse_range("KQo:0.7, JTs:0.4")
b = parse_range("KQo:0.5")
out = a.diff(b)
```

| Field | Value |
|---|---|
| `len(out)` | **16** (12 KQo + 4 JTs) |
| Distinct weights surfaced | `[0.2, 0.4]` |
| KQo per-combo weight | **0.2** (`= 0.7 − 0.5`) |
| JTs per-combo weight | **0.4** (untouched; not in `b`) |
| Wall | ~0.07 ms |

Confirms the per-combo `max(w_self − w_other, 0)` semantics across multiple
hand classes.

### Case 3 — all-unit back-compat

```python
a = parse_range("AA, KK")
b = parse_range("AA")
out = a.diff(b)
```

| Field | Value |
|---|---|
| `len(out)` | **6** (all KK combos) |
| Distinct weights surfaced | `[1.0]` |
| `diff.to_string()` (head) | `"KsKh, KsKd, KsKc, KhKd, KhKc, KdKc"` |
| Wall | ~0.05 ms |

When every combo on both sides has weight 1.0, `diff` reduces to boolean
set difference — exactly the pre-B10 behavior, so existing `Range.diff`
callers see no semantic change.

---

## Methodology

- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/feat-b10-phase-d-w2-2-persona`, branch `feat/b10-phase-d-w2-2-persona` off `origin/main` `1839ee1` (post-Phase-C).
- **Python:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python` (3.13, arm64).
- **Test runner:** `pytest tests/test_w2_2_per_combo_diff.py -v` → 4 passed in 0.03 s.
- **Fixture runner:** `.venv/bin/python scripts_retest/w2_2_per_combo_diff_retest.py` → all 3 cases PASS with embedded assertions.
- **No engine code modified** in this PR; Phases A/B/C already shipped the
  required mechanics. Phase D is a verification-only PR.

---

## References

- Plan: `docs/b10_per_combo_frequency_plan_2026-05-28.md`
- Phase A PR: **#149** (`40ac87a`) — `feat(range): per-combo fractional weights (B10 Phase A core, #60)`
- Phase B PR: **#154** (`11e3f01`) — `feat(range): aggregator + solver weight propagation (B10 Phase B, #60)`
- Phase C PR: **#158** (`1839ee1`) — `feat(ui): per-combo intensity editor (B10 Phase C, #60)`
- Prior persona snapshot: `docs/persona_status_2026-05-28-late.md`
- Phase A round-trip locked: `tests/test_range_frac_freq.py::test_to_string_round_trip_kqo_quarter`
