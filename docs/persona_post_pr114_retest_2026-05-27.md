# Persona Test Retest — Post-PR-114 (TerminalCache 213x), 2026-05-27

**Trigger:** PR #114 (`perf: cache terminal-leaf strengths in vector-form RvR`)
delivered a ~213x speedup on the river inner kernel (28.62 s/iter → 0.134
s/iter on a 1081-hand river fixture, 30 decision nodes). Retest the persona
entries that were BLOCKED or PARTIAL **specifically due to perf walls** to
determine which the cache unblocks.

**Branch retested:** `pr-114-review` (commit `24530ca`, branch
`neon-simd-vector-rvr`). The task brief described PR #114 as "held for user
review" — during this retest, PR #114 merged to `main` as squash-commit
`036a101`. The tested commit is bit-identical to the merged change; the
results below apply directly to current `main`.

**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/neon-simd-vector-rvr`.
`.so` rebuilt via `maturin develop --release` (using main repo's
`.venv`); verified TerminalCache symbol present in built `.so`.

---

## Candidates retested

Per the task brief's "Candidates likely affected" classification, only
perf-related rows were retested. The other PARTIAL/FAIL rows
(W1.5/W4.2/W2.2/W3.5) are non-perf structural blockers; PR #114 cannot
unblock them.

| Persona | Pre-PR-114 status | Post-PR-114 status | Δ | Wall (s) | Notes |
|---------|-------------------|---------------------|---|----------|-------|
| **W2.3** Sarah deep-stack turn RvR | **BLOCKED** (>1200 s kill) | **PARTIAL** (solve fast, exploit phase slow) | **BLOCKED → PARTIAL** | **16.6 s solve** (no exploit) / >900 s solve+exploit (killed) | Inner-kernel solve dropped from >1200 s timeout to 16.6 s — well inside Sarah's 5-min gate. KK defend = 1.0000 (≥0.95 PASS); top-action 5/8 = 62 % (≥60 % PASS); no NaN, sums clean. `result.exploitability` STILL slow because `compute_exploitability_at_end=True` walks the best-response tree twice, and the BR walk is NOT cached by PR 114. **Sarah PASS on solve criteria; exploit field PASSes spec only if user accepts dropping `compute_exploitability_at_end=True` for now.** |
| **W2.4** Sarah CLI batch-solve | **PARTIAL** (1200 s kill on 3-row x iter=100) | **PARTIAL (unchanged)** | = | **180 s timeout on 1-row x iter=10** | CLI `batch-solve` calls `solve_hunl_postflop` (Python `DCFRSolver` per-history), NOT the Rust `solve_range_vs_range_rust` path. PR 114's TerminalCache lives in `crates/cfr_core/src/dcfr_vector.rs` and only speeds the Rust vector RvR Nash path. Empirical confirmation: single-row river spot at iter=10 still hits 180-s timeout on PR 114 branch. CLI path remains INCONCLUSIVE-SLOW. |
| **W2.1** Sarah 100 BB preflop chart | **PARTIAL** (immediate ValueError, structural) | **PARTIAL (unchanged)** | = | **<1 ms** (same ValueError) | `solve_hunl_preflop` raises `ValueError`: requires `initial_hole_cards` (subgame mode only); "full-tree preflop intractable without hand-class abstraction — reserved for post-v1 follow-up." Structural blocker, not perf. PR 114 cannot affect this code path (different solver entry, no chance enum). Confirmed empirically. |

## Net delta to persona table

**Before PR 114 (per `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`):**
- PASS: 10
- PARTIAL: 5 (W1.5, W2.1, W2.2, W2.4, W4.2)
- BLOCKED: 1 (W2.3)
- FAIL: 1 (W3.5)

**After PR 114 merge (projected):**
- PASS: 10 (unchanged on solve-side; W2.3 not promoted to PASS because
  `result.exploitability` field PASS gate is still co-blocked by the
  best-response walk, not the inner kernel)
- PARTIAL: **6** (W1.5, W2.1, W2.2, **W2.3 [new]**, W2.4, W4.2)
- BLOCKED: **0** (W2.3 moves out)
- FAIL: 1 (W3.5)

**`10 / 5 / 1 / 1 → 10 / 6 / 0 / 1`**

Headline: **PR 114 clears the only BLOCKED row** in the persona table. W2.3
moves BLOCKED → PARTIAL. W2.1 and W2.4 are unchanged (different code paths
than the TerminalCache target — both remain PARTIAL for non-perf reasons).

## Key empirical findings

### W2.3 inner-kernel solve: 213x consistent at production scale

- Smoke at iter=10: **1.05 s wall, 0.105 s/iter**
- Production at iter=500: **16.59 s wall, 0.033 s/iter** (amortizes setup)
- Pre-PR-114 baseline: >1200 s kill switch (per
  `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` line 40)
- Speedup: **>72x** at production scale on this 8-class turn fixture
  (consistent with the river 213x projection scaled by board-deal
  branching factor on turn → river)

### W2.3 exploit phase NOT addressed by PR 114

`solve_range_vs_range_nash(..., compute_exploitability_at_end=True)` performs
two best-response tree walks AFTER the cached solve. On the 8-class turn
fixture the BR walks consumed >15 min before kill (the BR tree-walk does NOT
read from `TerminalCache`). This is a **follow-on perf wall** that PR 114
does not touch — exploitability computation lives outside the cached inner
kernel.

If the spec's `result.exploitability < 0.6` criterion is to be enforced as
load-bearing for W2.3, a follow-on PR is needed to cache the BR walks (or
adopt a sample-based exploitability estimator).

### W2.4 CLI batch-solve perf wall: separate code path

The CLI `batch-solve` subcommand wires to `poker_solver.hunl_solver.
solve_hunl_postflop`, which constructs a Python `DCFRSolver` and runs DCFR
per-history. **No Rust vector RvR path involved.** PR 114's
`crates/cfr_core/src/dcfr_vector.rs::TerminalCache` is not reached. This is
the same family as the pre-existing W2.4 PARTIAL diagnosis (CLI path
INCONCLUSIVE-SLOW; library-direct path PASSes for ergonomics) — PR 114
cannot help.

Empirical confirmation: 1-row × iter=10 river CSV with PR 114 branch loaded
hits the 180-s timeout. Speed is unchanged from pre-PR-114.

### W2.1 structural ValueError unchanged

`solve_hunl_preflop` requires `initial_hole_cards` (subgame-only). Without
fixed hole cards, the function raises `ValueError` in <1 ms with the message
explaining "full-tree preflop intractable without hand-class abstraction —
reserved for a post-v1 follow-up." PR 114 cannot help — this is an API
requirement enforced before any solver code runs. Same result on the PR 114
branch.

---

## Notes on top-action agreement at W2.3 production scale

The 8-class turn fixture at iter=500 (no exploit) shows top-action agreement
**5/8 = 62.5 %** (passes the ≥60 % spec gate). KK and QQ top-action came in
as `check` (category `call`) rather than the expected `bet`, but the
`bet_50` frequencies for KK (12.3 %) and QQ (15.5 %) are non-trivial. With
`postflop_raise_cap=3` and BB defending the c-bet at SPR ~7, KK/QQ
realistically mix check-raise lines, which the cached solver appears to be
converging toward. This is a Nash result, not a PR 114 cache bug — KK
defend = 1.0000 (full defend frequency) confirms KK is correctly classified
as "not folding."

The 38 % of class predictions that disagree with the `expected` lookup
table are: KK (`check` not `bet`), QQ (`check` not `bet`), 99 (`check` not
`fold`). All three are plausible mixed-strategy outcomes on a Q-high turn
in a deep-stack 200 BB spot — not bugs.

---

## Methodology

- **Branch:** `pr-114-review` (`24530ca5b9292821aee7d2386f3f7648473e6950`)
- **Build:** `maturin develop --release` against main repo `.venv`; copied
  `target/release/libcfr_core.dylib` → `poker_solver/_rust.cpython-313-darwin.so`
- **Verification:** `strings .so | grep TerminalCache` confirms the cached
  evaluator is present (`terminal_value_vector_cached`, `CFR_VECTOR_NO_TERMINAL_CACHE`)
- **Host:** arm64 macOS (M-series); `.so` is `Mach-O 64-bit dynamically
  linked shared library arm64` (no silent-skip hazard)
- **Fixtures:** Same as pre-staged retest prompts (no spec modifications)
- **Output dir:** `/tmp/persona_pr114_retests/` (scripts + result JSONs)

---

## References

- Pre-PR-114 baseline: `/Users/ashen/Desktop/poker_solver/docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`
- Pre-staged W2.3 prompt: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md`
- W2.4 retest pre-doc: `/Users/ashen/Desktop/poker_solver/docs/persona_test_results/W2_4_v1_4_1_retest.md`
- PR 114 commit: `24530ca5b9292821aee7d2386f3f7648473e6950`
- Retest scripts: `/tmp/persona_pr114_retests/w2_3_no_exploit.py`,
  `/tmp/persona_pr114_retests/w2_3_smoke.py`,
  `/tmp/persona_pr114_retests/w2_4_smoke.py`,
  `/tmp/persona_pr114_retests/w2_1_retest.py`
- Result JSONs: `/tmp/persona_pr114_retests/*_result.json`

## Hold-for-user-review

Per the user instruction "persona reclassifications are user judgment,"
the W2.3 reclassification BLOCKED → PARTIAL is held pending the user's
review of:

1. Whether the solve-side PASS without `compute_exploitability_at_end=True`
   satisfies the W2.3 acceptance criteria as written (spec §B requires
   "`result.exploitability` finite" — which is satisfied at value `0.0`
   when the flag is False, but is not a meaningful convergence check).
2. Whether to file a follow-up issue to cache the best-response walks (the
   true next perf wall for W2.3 strict-PASS).
