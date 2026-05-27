# Persona Retest — W1.5 (Marcus) — 2026-05-26

## Brief

- **Workflow:** W1.5 "Why did the solver say to fold 76s preflop at 10 BB?"
- **Persona:** Marcus (recreational player; <30 s interactive gate)
- **Prior verdict:** PARTIAL — Type C-NICE — "no standalone retest doc, `return_ev=True` decomposition not yet added"
  (per `docs/persona_test_status_2026-05-26.md:53` and `docs/persona_status_post_v1_8_2026-05-26.md` P3)
- **Spec:** `docs/pr13_prep/persona_acceptance_spec.md:37` —
  > `get_pushfold_strategy(10, 'sb_jam', '76s')` returns a frequency; no EV decomposition. Expected ~1.0 jam (76s has ~38 % equity vs wide; jams are +EV at 10 BB except vs tight Nash). `WORKS-BUT-DOCS-CONFUSING` if chart agrees with intuition; `BUG` candidate if not. Fix: add `return_ev=True` keyword returning `(freq, ev_jam_bb, ev_fold_bb)`. Severity: low.
- **Fixture:** none in `docs/persona_test_results/` or `docs/pr13_prep/`; this retest probes the public API directly per the spec entry. Documented procedure rather than a captured fixture file (consistent with the prior snapshot's "no standalone retest doc" note).

## Execution

- Interpreter: `/Users/ashen/Desktop/poker_solver/.venv/bin/python` (CPython 3.13.1)
- Wall-clock: ~10 s total for all probes
- Mode: read-only, public API only

### Probe 1 — chart cell at the brief's depth

`get_pushfold_strategy(10, 'sb_jam', '76s') = 1.0000`
Lookup time: **5.6 ms** (Marcus gate <50 ms — 9 x headroom)

### Probe 2 — signature inspection (return_ev kwarg)

API signature: `get_pushfold_strategy(stack_bb: int, position: str, hand: str) -> float`
`return_ev` parameter present: **False**

→ The spec's named fix (EV decomposition kwarg) has **not** shipped between PR 39 (v1.7.0 CLI wrapper) and v1.8 / today. No `(freq, ev_jam_bb, ev_fold_bb)` tuple path exists.

### Probe 3 — neighbor sanity (10 BB SB jam)

| Hand | freq | Hand | freq |
|---|---|---|---|
| 76s | 1.0000 | T9s | 1.0000 |
| 87s | 1.0000 | 22 | 1.0000 |
| 65s | 1.0000 | 33 | 1.0000 |
| 54s | 1.0000 | 44 | 1.0000 |
| 86s | 1.0000 | A2o | 1.0000 |
| 97s | 1.0000 | A5o | 1.0000 |
| 75s | 1.0000 | K2s | 1.0000 |

All suited connectors 54s—98s are pure jams at 10 BB SB. Chart aggregate at this depth: 111 pure jams / 56 pure folds / 2 mixed (i.e., a wide ~66 % aggressive SB chart, consistent with Sklansky–Chubukov / Nash for HU 10 BB).

### Probe 4 — 76s SB-jam depth scan (2–15 BB)

76s SB-jam is a **pure jam (freq 1.0000) at every supported depth, 2 BB through 15 BB**. There is no depth at which the chart folds 76s in the SB jam role.

### Probe 5 — heads-up equity sanity (why 76s is +EV to jam)

| Villain | 76s equity (exact enum) |
|---|---|
| AA | 0.2306 |
| TT | 0.2162 |
| 99 | 0.2043 |
| 88 | 0.1908 |
| 77 | 0.1835 |
| AKs | 0.3951 |
| AQo | 0.4167 |
| KQs | 0.3901 |
| A2s | 0.4666 |

→ Against a typical 10 BB BB-call range (broadways + medium pairs + suited aces), 76s holds roughly 35–45 % share. With dead money in the pot (SB + BB blinds + antes) and BB folding the worse part of its defense, the Sklansky–Chubukov / Nash math makes 76s a clear +EV jam at 10 BB. The chart and the heuristic agree.

## Verdict

**PARTIAL — unchanged from the 2026-05-26 baseline.**

The classification stays at PARTIAL / Type C-NICE because:

1. The chart itself is **correct and obviously +EV-rationalizable** — 76s pure-jams at 10 BB; the brief's premise ("why does 76s **fold** at 10 BB?") is counterfactual relative to the shipped chart. So there is no correctness bug to fix.
2. The named spec fix — `return_ev=True` returning `(freq, ev_jam_bb, ev_fold_bb)` — **has not shipped**. Marcus still gets back a single float frequency and cannot inspect the EV decomposition that would answer "why" without external Sklansky–Chubukov knowledge.

This is the textbook **`WORKS-BUT-DOCS-CONFUSING`** pattern from the spec entry: the answer is right, but the user can't see *why* through the API. v1.8 did nothing to move this (and was not expected to per the v1.8 decision brief).

### Type classification

**Type C-NICE** (unchanged).

- Not Type A (no correctness bug; chart says JAM, JAM is right per equity + dead-money math).
- Not Type B or C-CRIT (no broken/missing capability blocks Marcus — he can still get the chart answer and act on it inside his 30 s budget; the EV decomposition is purely explanatory).
- Not C-USEFUL (the missing kwarg is genuinely nice-to-have for a curious recreational user; Marcus's primary use case — "what does the chart say?" — is fully served).

Per `feedback_persona_test_rectification`, Type C-NICE is low-priority, deferred-OK, no ship pressure. This matches the prior snapshot's framing.

## Marcus time-budget check

| Gate | Measured | Margin |
|---|---|---|
| Lookup latency <50 ms | 5.6 ms | 9 x |
| Session <30 s | <1 s end-to-end | >30 x |

Marcus's interactive gate is comfortably met. No perf concerns. v1.8 SIMD (~1.0 x on M4 Pro arm64 per `docs/v1_8_simd_perf_benchmark_2026-05-26.md`) is structurally irrelevant to chart lookup — this is a dict-get, not a kernel solve.

## Next step (if/when picked up)

Per `docs/pr13_prep/persona_acceptance_spec.md:37`, the named fix is:

```python
def get_pushfold_strategy(
    stack_bb: int,
    position: str,
    hand: str,
    *,
    return_ev: bool = False,
) -> float | tuple[float, float, float]:
    """When return_ev=True, return (freq, ev_jam_bb, ev_fold_bb)."""
```

EV computation against the chart's implied villain call/fold ranges is straightforward (the chart already encodes BB call frequencies; pot odds at jam are fixed by stack / SB / BB / ante config). A docs-only USAGE.md §3a paragraph explaining "the chart is +EV by construction; here is the Sklansky–Chubukov reasoning" would also discharge the spec's `WORKS-BUT-DOCS-CONFUSING` framing at lower cost.

No ship pressure either way — Type C-NICE.

## Aggregate impact on snapshot

`docs/persona_test_status_2026-05-26.md` Marcus row stays:

| ID | Description | Verdict | Latest retest | Blocker / next step |
|---|---|---|---|---|
| W1.5 | "Why does 76s fold at 10 BB?" — sanity-check chart | **PARTIAL** | `docs/persona_w1_5_retest_2026-05-26.md` *(this doc)* | `return_ev=True` decomposition not yet added. Type C-NICE. Chart says pure-jam; +EV by Sklansky–Chubukov / equity math; no correctness gap. |

Pre-retest tally (per `persona_test_status_2026-05-26.md:5`): 9 PASS / 5 PARTIAL / 2 BLOCKED / 1 FAIL.
Post-retest tally: **unchanged.** W1.5 stays PARTIAL.

## References

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr13_prep/persona_acceptance_spec.md:37`
- API: `/Users/ashen/Desktop/poker_solver/poker_solver/pushfold.py:125`
- CLI wrapper (PR 39, v1.7.0): `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py:707`
- USAGE.md §3a: `/Users/ashen/Desktop/poker_solver/USAGE.md:82`
- Prior status: `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-26.md:53`
- Rectification framework: `feedback_persona_test_rectification` (Type C-NICE definition)
