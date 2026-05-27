# W2.4 — Sarah batch-solve CSV — 2026-05-26 retest

**Date:** 2026-05-26
**Tester:** automated agent (P3 priority from `persona_test_status_2026-05-26.md`)
**Persona / workflow:** Sarah — provides a CSV of HUNL solve specs, invokes
`poker-solver batch-solve`, expects the library to populate with one entry per
row, round-trip-retrievable strategy, within Sarah's 15-min session budget.
**Spec source:** `docs/pr13_prep/persona_acceptance_spec.md` §W2.4
**Prior retest:** `docs/persona_test_results/W2_4_v1_4_1_retest.md` (PARTIAL —
library-direct PASS, CLI real-solve INCONCLUSIVE-SLOW)
**Trigger:** post-v1.8 SIMD retest cycle per `feedback_post_ship_persona_retest`.

---

## Verdict

**PARTIAL — UNCHANGED from v1.4.1.** Library-direct path PASS (3/3
round-trip in 6.1 ms); CLI `batch-solve --dry-run` PASS (3 spots parsed,
spot_ids bit-identical to library-direct path); CLI real-solve path
**INCONCLUSIVE-SLOW** (1-row, 1-iter probe did not return within 90 s —
same diagnosis as v1.4.1: solver setup cost dominates per-iteration
cost on the river full-range tree).

**Type:** D (timeout / perf-bound; v1.8 SIMD did not deliver the projected
unblock, consistent with `v1_8_simd_perf_benchmark_2026-05-26.md` measuring
~1.0× on real workloads).

**Net change vs v1.4.1:** none in verdict or type. The retest is now logged
as the post-v1.8 confirmation that Sarah's batch-solve CLI perf is still
gated on the W2.3-family setup-cost cliff, not a v1.8-amenable hot loop.

---

## Procedure

1. **Library-direct path** — built 3 `SpotDescription`s (river, 100 BB,
   bet sizes `0.5, 1.0`), wrote stub `SolveResult`s, called
   `Library.put` × 3, then `Library.get` + `list` + `stats` to verify
   round-trip integrity. Script: `/tmp/w24_2026_05_26/w24_library_direct.py`.
2. **CLI dry-run path** — `python -m scripts.batch_solve --input … --dry-run`
   on the 3-row CSV. Verified `spot_id` agreement with the library-direct
   path (CSV-driven canonicalization equivalence).
3. **CLI real-solve path** — single-row, **1-iteration** probe with a
   strict 90 s subprocess timeout. Identical fixture shape to the v1.4.1
   minimal-scope probe (a guardrail to characterize setup cost, not the
   full 500-iter batch).

All commands run with `.venv/bin/python` (Python 3.13, macOS arm64).

---

## CSV layouts

`/tmp/w24_2026_05_26/w24_spots.csv` (3 rows; river street, matches v1.4.1
fixture exactly):

```csv
name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations
srp_river_AsTc5dKh3c,river,AsTc5dKh3c,100,"0.5,1.0",,500
srp_river_KsQd9h5c2s,river,KsQd9h5c2s,100,"0.5,1.0",,500
srp_river_7d6s5h4c3d,river,7d6s5h4c3d,100,"0.5,1.0",,500
```

`/tmp/w24_2026_05_26/w24_one_iter.csv` (1 row, 1 iter — minimal probe):

```csv
name,starting_street,initial_board,stacks_bb,bet_sizes,abstraction_path,iterations
srp_river_AsTc5dKh3c_1iter,river,AsTc5dKh3c,100,"0.5,1.0",,1
```

---

## Results

### Library-direct path (PASS)

```
BUILD ms=0.098
PUT ms=5.220
GET/LIST/STATS ms=0.828
TOTAL ms=6.146

STATS total_count=3 by_street={'river': 3}
LIST returned 3 entries
  - id=8aafebf7ea69f2b7 label='srp_river_7d6s5h4c3d' street=river stack_bb=100 expl=0.01
  - id=f84cfa21baaef921 label='srp_river_KsQd9h5c2s' street=river stack_bb=100 expl=0.01
  - id=dffe28124470b008 label='srp_river_AsTc5dKh3c' street=river stack_bb=100 expl=0.01

INTEGRITY: 3/3 round-trip equal
VERDICT: PASS
```

Total wall-clock **6.1 ms**, well under Sarah's 15-min budget. Bit-identical
to v1.4.1 (5.5 ms then, 6.1 ms now — within noise; same `spot_id`s).

### CLI `--dry-run` path (PASS)

```
[DRY-RUN] srp_river_AsTc5dKh3c dffe28124470b008…686b1ff3 (would solve)
[DRY-RUN] srp_river_KsQd9h5c2s f84cfa21baaef921…ff9d8351c (would solve)
[DRY-RUN] srp_river_7d6s5h4c3d 8aafebf7ea69f2b7…576edefa (would solve)
Summary: total=3 ok=0 skip=0 dry_run=3 oom=0 error=0
```

Wall-clock <1 s. `spot_id`s **bit-identical** to library-direct output
(first 16 hex chars match for all 3 rows), confirming CSV-driven
canonicalization parity unchanged since v1.4.1.

### CLI real-solve path (INCONCLUSIVE-SLOW)

| Probe | Config | Wall-clock | Outcome |
|---|---|---:|---|
| 1-row, 1-iter | `/tmp/w24_2026_05_26/w24_one_iter.csv` | **timeout @ 90 s** | No completion; no `[OK]` lines emitted; no partial stdout. |
| 1-row, 1-iter (re-probe at 30 s budget) | same | timeout @ 30 s | Confirms no partial output ever emitted (so it's setup cost, not per-iter cost — same diagnosis as v1.4.1). |

The 3-row × 500-iter batch was **not attempted** at this retest (per the
v1.4.1 finding it hits the 10-min agent timeout, and that finding stands
post-v1.8 by the SIMD ~1.0× refutation).

---

## Diagnosis

Identical to v1.4.1: the CLI's real-solve path delegates to
`solve_hunl_postflop` for each row; river full-range subtree build at 100 BB
deep with a 2-bet menu is the perf-dominant phase, **before** any CFR
iteration runs. v1.8 SIMD (`docs/v1_8_simd_perf_benchmark_2026-05-26.md`)
measured **~1.0× on real workloads** (936 ms/iter v1.7.0 → 942 ms/iter v1.8
for 1081-hand river RvR @ 3 actions; 4,777 → 4,723 ms/iter @ 5 actions),
which confirms there was no hidden setup-cost win to be had. The
W2.4 CLI perf cliff is structural and will remain bound until the v1.9
EMD bucketing work lands (per `v1_8_decision_brief.md:26`).

The **library subsystem itself** — Sarah's reproducibility/persistence
cornerstone — is **healthy**: deterministic `spot_id`s, round-trip
strategy/game_value/iterations preservation, dry-run + library-direct
spot_id parity.

---

## Path-by-path verdict

| Path | Verdict | Wall-clock |
|---|---|---:|
| `Library.open/put/get/list/stats` direct API | **PASS** | 6.1 ms total |
| `poker-solver batch-solve --input csv --dry-run` | **PASS** | <1 s |
| `poker-solver batch-solve --input csv` (real solve, 1 row, 1 iter) | **INCONCLUSIVE-SLOW** | >90 s, no completion |

---

## Comparison to v1.4.1

| Metric | v1.4.1 (2026-05-23) | 2026-05-26 retest | Delta |
|---|---|---|---|
| Library-direct round-trip total | 5.5 ms | 6.1 ms | ~noise |
| Library-direct integrity | 3/3 | 3/3 | unchanged |
| `spot_id` (row 1) | `dffe28124470b008…` | `dffe28124470b008…` | **bit-identical** |
| `spot_id` (row 2) | `f84cfa21baaef921…` | `f84cfa21baaef921…` | **bit-identical** |
| `spot_id` (row 3) | `8aafebf7ea69f2b7…` | `8aafebf7ea69f2b7…` | **bit-identical** |
| Dry-run | PASS, <5 s | PASS, <1 s | improved (within noise) |
| CLI real-solve 1-row 1-iter | timeout @ 90 s | timeout @ 90 s | **unchanged** |

The bit-identical `spot_id` agreement between v1.4.1 and today confirms
**no canonicalization drift** in the library schema, despite intervening
PRs and v1.8 SIMD work.

---

## Aggregate snapshot impact

W2.4 verdict in `docs/persona_test_status_2026-05-26.md` was `PARTIAL`
(BLOCKED on CLI real-solve path). This retest **reconfirms** that status.
No reclassification is owed. The snapshot's "Sarah time budget" line —
"v1.8 SIMD did not deliver the projected acceleration; W2.3 / W2.4 perf
characterization owed" — is now satisfied for W2.4.

---

## Artifacts

- `/tmp/w24_2026_05_26/w24_spots.csv` (3-row CSV; transient)
- `/tmp/w24_2026_05_26/w24_one_iter.csv` (1-row 1-iter probe; transient)
- `/tmp/w24_2026_05_26/w24_library_direct.py` (round-trip script; transient)
- `/tmp/w24_2026_05_26/w24_library.db` (SQLite library with 3 entries; transient)

## Reproduction

```bash
# 1. Library-direct path (PASS, ~6 ms)
PYTHONPATH=. .venv/bin/python /tmp/w24_2026_05_26/w24_library_direct.py

# 2. CLI dry-run path (PASS, <1 s)
PYTHONPATH=. .venv/bin/python -m scripts.batch_solve \
    --input /tmp/w24_2026_05_26/w24_spots.csv \
    --library-path /tmp/w24_2026_05_26/w24_library_cli.db \
    --dry-run

# 3. CLI real-solve probe (INCONCLUSIVE-SLOW; timeout @ 90 s expected)
PYTHONPATH=. .venv/bin/python -m scripts.batch_solve \
    --input /tmp/w24_2026_05_26/w24_one_iter.csv \
    --library-path /tmp/w24_2026_05_26/w24_library_cli.db
```

---

## References

- Prior retest: `docs/persona_test_results/W2_4_v1_4_1_retest.md`
- Spec: `docs/pr13_prep/persona_acceptance_spec.md` §W2.4
- Persona status snapshot: `docs/persona_test_status_2026-05-26.md`
- v1.8 SIMD bench (load-bearing for "no unblock available"):
  `docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- v1.9 EMD bucketing roadmap (eventual structural unblock):
  `docs/v1_8_decision_brief.md:26`
- Batch-solve CLI: `poker_solver/cli.py:672` + `scripts/batch_solve.py`
- Library API: `poker_solver/library.py` (`SpotDescription`, `Library.put/get/list/stats`)
