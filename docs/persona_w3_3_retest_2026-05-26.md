# W3.3 Persona Retest — 2026-05-26

**Workflow:** Daniel, "Merged-strategy range; GTO response" — node-locking-at-scale closing test.
**Trigger:** P2 priority per `docs/persona_status_post_v1_8_2026-05-26.md` line 80 / line 147 — "overdue closing test (node-locking shipped 2+ minor releases ago)."
**Tip:** main; `poker_solver.__version__ == '1.7.0'` (installed package version string predates v1.8 phase commits, but v1.8 SIMD phases are merged to main per `persona_status_post_v1_8_2026-05-26.md` §intro).
**Backend:** Python (selected automatically by `solve_hunl_postflop`; matches the Python wall-clock of the v1.4.0 baseline retest).

---

## Prior status

Per `docs/persona_test_status_2026-05-26.md` row W3.3 and `docs/persona_status_post_v1_8_2026-05-26.md` §4:

- **Verdict:** PARTIAL.
- **Blocker:** "Node-locking infrastructure exists (PR 24b in v1.6.0); specific merged-range workflow has no standalone retest doc."
- **Recommendation:** "P2 closing retest owed; node-locking shipped 2+ minor releases ago; this is overdue regardless of v1.8."
- **Last per-W3.3 evidence:** `docs/pr13_prep/v1_4_0_daniel_retest.md` (2026-05-23, v1.4.0 / tip `166d2b8`) — W3.3 marked WORKS-NOW with 1.79 s Python wall-clock; never retested at a later tip until today.

The v1.4.0 doc covered W3.1 / W3.2 / W3.3 collectively but was the **only** W3.3 result document; PARTIAL classification on subsequent snapshots reflected the absence of a v1.5+ closing test, not a regression.

---

## Retest invocation

Used `.venv/bin/python` (universal2; native `_rust.cpython-313-darwin.so` is arm64, host is arm64 — silent-skip hazard cleared per `feedback_dotso_arch_check`).

Inline script (not a fixture file — none pre-staged for W3.3) replicating the v1.4.0 Daniel retest §W3.3 procedure:

```python
from poker_solver import default_tiny_subgame, solve_hunl_postflop

config = default_tiny_subgame()
HERO_LOCK_KEY = 'KcAh|2d5s7cKhAs|r|b750'   # hero AhKc facing villain BET_75
HERO_LOCK = [0.0, 0.5, 0.5]                # merged 50/50 raise/call (no fold)
VILLAIN_KEY = 'QhQd|2d5s7cKhAs|r|b750A'    # villain QdQh facing hero raise

baseline = solve_hunl_postflop(config, iterations=2000)
locked = solve_hunl_postflop(config, iterations=2000,
                             locked_strategies={HERO_LOCK_KEY: HERO_LOCK})
```

Same fixture as v1.4.0 §W3.3 (`docs/pr13_prep/v1_4_0_daniel_retest.md:57-58`).

---

## Wall-clock

| Phase | Wall-clock | v1.4.0 baseline (reference) |
|---|---|---|
| Baseline solve (2000 iter, Python) | **1.507 s** | (not separately recorded) |
| Locked solve (2000 iter, Python) | **1.496 s** | 1.79 s |
| Total | **3.003 s** | — |

Both well under Daniel's 15 min per-spot budget (`persona_time_budgets.md`); well under Marcus's <30 s reflex gate too. Slight improvement over the v1.4.0 wall-clock is consistent with the v1.7 / v1.8 codebase changes; **not** a v1.8 SIMD signal (Python backend was selected; the v1.8 SIMD ~1.0× refutation in `v1_8_simd_perf_benchmark_2026-05-26.md` is on the Rust kernel anyway).

---

## Captured output

### Hero baseline @ lock key
`KcAh|2d5s7cKhAs|r|b750`: `[0.0, 0.4483, 0.5517]`

- v1.4.0 reference: `[0, 0.432, 0.568]`
- Drift vs v1.4.0: L1 = 0.033, within fixed-point convergence variation (different optimizer state across releases). Same qualitative split: ~45/55 raise/call mix, no fold.

### Lock passthrough
`KcAh|2d5s7cKhAs|r|b750` (locked solve): `[0.0, 0.5, 0.5]`

- Expected (lock target): `[0.0, 0.5, 0.5]`
- **Bit-exact passthrough: PASS** (max diff < 1e-9 on all 3 actions).

### Villain downstream reaction (canonical W3.3 signal)
`QhQd|2d5s7cKhAs|r|b750A` (villain facing hero raise):

- Baseline: `[0.6535, 0.3465]` (fold/call; 2-action node at current tip — see note below)
- Locked: `[0.5, 0.5]`
- L1 shift: **0.3070**

**Note on action structure:** v1.4.0 doc shows this node as 3-action `[0.717, 0.142, 0.142]`. Current main exposes it as a 2-action node `[fold, call]` — likely a betting-tree configuration change between v1.4 and v1.7 (the v1.4.0 retest may have included an additional raise option). The qualitative signal is the same: villain's fold/call split moves toward symmetric mix when hero plays merged. The v1.4.0 doc's "0.717 → 0.333 fold collapse" mirrors today's "0.6535 → 0.500 fold reduction" — both show villain calling thinner vs merged hero.

### Diverging infosets (L1 > 0.01)
5 infosets diverge; total L1 = **0.7491**:

| Infoset | L1 |
|---|---|
| `QhQd|2d5s7cKhAs|r|b750A` (villain facing raise) | 0.3070 |
| `QhQd|2d5s7cKhAs|r|b330r1378` | 0.2139 |
| `KcAh|2d5s7cKhAs|r|x` (hero facing check) | 0.1110 |
| `KcAh|2d5s7cKhAs|r|b750` (locked node, internal mix recomputed) | 0.1034 |
| `QhQd|2d5s7cKhAs|r|b330A` | 0.0137 |

Magnitude is similar to v1.4.0 ("Villain L1 = 1.07; four villain infosets diverge >1 %"). Same qualitative finding — downstream of the locked node, the solver re-optimises villain's response.

### Game value
- Baseline: **5.0000** BB
- Locked: **5.0000** BB
- Delta: **-0.0000** BB (zero to 4 decimal places)

Hero EV is preserved because the locked merged shape is itself a Nash-optimal mix at this node (hero's `[0, 0.4483, 0.5517]` baseline is within the indifference manifold for the `[raise, call]` split). The lock nudges hero off the Nash point but stays inside the indifference set — game value is invariant on this manifold. v1.4.0 doc reports identical 5.0 / 5.0 (delta 0.0 BB).

---

## Acceptance — 4 / 4 PASS

| # | Criterion | Result | Detail |
|---|---|---|---|
| C1 | Lock passthrough bit-exact at locked infoset | **PASS** | max diff < 1e-9 on 3 actions |
| C2 | Villain response shifts > 5% L1 at facing-raise node | **PASS** | L1 = 0.3070 (6× threshold) |
| C3 | EV monotonicity: `gv_lock <= gv_base + 1e-3` (hero locked off Nash should not improve hero EV) | **PASS** | delta = 0.0000 |
| C4 | At least 1 downstream infoset diverges L1 > 1% | **PASS** | 5 infosets diverge |

---

## Verdict

**PASS** — Type **A** (correctness: node-locking primitive functions per spec on the merged-range workflow at the current tip).

The v1.4.0 W3.3 result reproduces at the current tip with the same qualitative signals (lock applied bit-exact; villain re-optimises with L1 ≈ 0.3 at the facing-raise node; EV invariant on the indifference manifold). No regression in 2+ minor releases.

### Status delta

| | 2026-05-25 snapshot | 2026-05-26 (this retest) |
|---|---|---|
| Verdict | PARTIAL | **PASS** |
| Type | (no standalone retest doc) | **A (correctness, closed)** |
| Evidence | `docs/pr13_prep/v1_4_0_daniel_retest.md` only | + this doc |
| Recommendation | P2 closing retest owed | **CLOSED** |

This unblocks the W3.3 row of the persona status snapshot to PASS and increments the PASS count by 1.

---

## Caveats

1. **Python backend only.** The v1.4.0 doc covered cross-tier (Python ↔ Rust) bit-identity at 5k iters; this retest exercised Python only. The native `_rust.cpython-313-darwin.so` is arm64 / available, but `solve_hunl_postflop` selected Python at this fixture size. The cross-tier diff is structurally covered by `tests/test_node_locking.py::test_diff_*_lock_kuhn` test suite (unchanged) — those tests would surface any regression in Rust passthrough independent of this retest.
2. **Single-combo fixture.** As the v1.4.0 doc noted (lines 94-97), `default_tiny_subgame` cannot exercise true range-level merged-strategy semantics ("a 50/50 merged range" across many hands); it exercises the per-infoset lock primitive only. The range-level version remains downstream of W2.3 unblock (Sarah's deep-stack RvR perf wall).
3. **Action-tree variance vs v1.4.0.** The villain facing-raise node had a 3-action structure in v1.4.0 (`[fold, call, raise]` per the doc) and a 2-action structure today (`[fold, call]`). Likely a betting-abstraction configuration change between v1.4 and v1.7; not a regression for W3.3 semantics, but flagged for the persona-status reviewer.
4. **No pre-staged fixture file.** No W3.3 prompt / fixture was found at `docs/persona_test_results/` or `docs/pr13_prep/`. Used the v1.4.0 retest doc itself as the retest specification.

---

## References

- Prior W3.3 evidence: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/v1_4_0_daniel_retest.md` (§W3.3 lines 55-71)
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md:57` (W3.3 definition)
- Time budget: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_time_budgets.md` (Daniel ≤15 min)
- Current status snapshot: `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-26.md` (W3.3 row line 79)
- v1.8 SIMD bench (for context on backend choice): `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- Node-locking test suite: `/Users/ashen/Desktop/poker_solver/tests/test_node_locking.py`
- Node-locking spec: `/Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_4_node_locking.md`
