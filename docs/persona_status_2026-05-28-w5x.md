# Persona Test Status Snapshot — 2026-05-28 (W5.x Premium-A workflows added)

**Trigger:** Audits #69 (v1.9.0) and #71 (v1.10.0) both flagged that the
audit table claimed Wendy (Premium-A consumer) coverage existed but the
W5.x workflows had never been authored. This snapshot adds the five W5.x
persona tests via `tests/test_w5_premium_a_personas.py`, bumping the
scope total from 17 (W1.x / W2.x / W3.x / W4.x = 5+5+5+3) to 22
(+W5.1-W5.5).

**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/feat-w5-persona-tests-premium-a`
(branch `feat-w5-persona-tests-premium-a` off `origin/main` `b5aa023`).

**Prior snapshot:** `docs/persona_status_2026-05-28-evening.md`:
**17 PASS / 0 PARTIAL / 0 BLOCKED / 0 FAIL** (W1.x + W2.x + W3.x + W4.x,
scope = 17).

---

## Bottom line

| Category | Count | Workflows |
|---|---|---|
| **PASS** | **22** | W1.1, W1.2, W1.3, W1.4, W1.5, W2.1, W2.2, W2.3, W2.4, W2.5, W3.1, W3.2, W3.3, W3.4 (caveated), W3.5, W4.1, W4.2, W4.3, **W5.1** (new), **W5.2** (new), **W5.3** (new, synthetic-fixture caveat), **W5.4** (new), **W5.5** (new) |
| **PARTIAL** | **0** | — |
| **BLOCKED** | **0** | — |
| **FAIL** | **0** | — |

**Net delta vs prior snapshot:** PASS 17 → **22** (+5: all five W5.x
workflows), PARTIAL 0 → 0 (=), BLOCKED 0 → 0 (=), FAIL 0 → 0 (=).
Scope total = 22.

**Five new reclassifications:**

| Workflow | Prior | Now | Driver |
|---|---|---|---|
| **W5.1** Blueprint casual lookup (100 BB / no-ante / AKs) | unscoped | **PASS** | **PR #174** (`509f07d`, `feat(blueprint): loader API + manifest discovery + lazy load (Phase 2, #68)`) |
| **W5.2** Interpolated depth lookup (67 BB convex blend of 60/80 BB) | unscoped | **PASS** | **PR #173** (`cb177c7`, `feat(blueprint): stack-depth interpolation module (Phase 3, #68)`) + **PR #181** (`03842b0`, router dispatch) |
| **W5.3** Blueprint → postflop chained on Qs 7h 2d (synthetic-fixture) | unscoped | **PASS** (wiring contract); production-scale **caveated** | **PR #177** (`18b9bcf`, postflop subgame wiring) + **PR #182** (`2aedb4b`, b/r token normalization) + **PR #181** (router dispatch) |
| **W5.4** Custom range fallback (B10 override forces live solve) | unscoped | **PASS** | **PR #181** (`_decide_route` rule 2) + **B10 Phase A/B/C** (PRs **#149** / **#154** / **#158**) |
| **W5.5** Ante toggle materially shifts strategy at 40 BB | unscoped | **PASS** | 27-shard `assets/blueprints/` bundle (chore commit `1783bef`) + **PR #174** (loader handles all 3 ante tokens via `normalize_ante`) |

---

## W5.x harness details

**Test file:** `tests/test_w5_premium_a_personas.py` (13 test functions
covering the 5 workflows; W5.1 has 3 tests for route/perf/coverage, W5.2
has 3 for route/blend/edge, W5.3 has 2 for solve/dispatch, W5.4 has 3
for the three live-solve-forcing triggers, W5.5 has 2 for the L1-shift
and no-error invariants).

**Spec amendment:** `docs/pr13_prep/persona_acceptance_spec.md` §2 adds
the Wendy persona block + W5.1-W5.5 workflow entries. The scope
total in §"Scope" line bumps 18 → 23 (the original 18 + 5 Wendy
workflows). Per-workflow PR enablers are cited inline in each W5.x
spec line.

**Wall time:** **1.13 s total** for all 13 tests on M-series silicon
(`/Users/ashen/Desktop/poker_solver/.venv/bin/python` 3.13, arm64).
Sub-second for W5.1/W5.2/W5.4/W5.5; ~1 s for the W5.3 synthetic
postflop solve (30 iters on a 2-class fixture).

**Drivers:** test fixtures consume the shipped 27-shard
`assets/blueprints/` bundle (manifest schema v1.0, 9 depths × 3 antes).
W5.3 additionally builds a synthetic 2-class blueprint per the wiring
test pattern — see the §"W5.3 caveat" block below.

---

## W5.3 caveat — production-scale blocked on v1.10 perf

Per `docs/flop_subgame_perf_measurement_2026-05-28.md`, the postflop
subgame solver currently OOMs (peak RSS 2.3-2.9 GB) or hits the 20-min
hard timeout at **every** production-scale configuration tested,
including the **floor fixture** at `top_k=2 / iter=2 / 3-class-hero ×
2-class-villain`. The shipped 169-class blueprint's expansion + flop
tree explosion is the bottleneck.

W5.3 in this snapshot validates the **wiring contract** (preflop
blueprint → 1326 expansion → postflop subgame Nash) using a synthetic
2-class blueprint mirroring `test_solve_postflop_from_blueprint_end_to_end_flop`
in `tests/test_blueprint_subgame_wiring.py`. The synthetic fixture
runs in <2 s and exercises the same three pipeline stages.

**Follow-up (v1.10):** once the `docs/v1_10_postflop_optimization_plan.md`
roadmap PRs land (vector-form flop forward walk, rayon-parallel chance
branches, NEON SIMD vector RvR, arena LTO), retarget
`test_w5_3_postflop_chained_q72_smoke` at the **shipped** blueprint
with `hero_classes=['KK','QQ','AA']` and a wider villain set. The
current spec line in `docs/pr13_prep/persona_acceptance_spec.md` W5.3
already marks the production-scale shift as a deferred follow-up.

---

## Per-workflow table

### Marcus (W1.x) — 5/5 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28-evening.md`.

### Sarah (W2.x) — 5/5 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28-evening.md`.

### Daniel (W3.x) — 5/5 PASS *(no movement, W3.4 caveat carries forward)*

Unchanged from `persona_status_2026-05-28-evening.md`.

### Priya (W4.x) — 3/3 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28-evening.md`.

### Wendy (W5.x) — 5/5 PASS *(new persona; all five workflows ship at PASS)*

| ID | Verdict | Wall | Assertion |
|---|---|---|---|
| W5.1 | **PASS** (new) | warm-cache lookup **<100 ms** (typically <1 ms post-warm); full 13-test suite 1.13 s | `SolverRouter.solve(stack_bb=100, ante='none', hand='AKs', action_history='')` routes to `blueprint_lookup`, `confidence='exact'`, 10 representative cells all populate non-degenerate simplex-valid strategies. Enabled by **PR #174** (BlueprintLoader). |
| W5.2 | **PASS** (new) | <1 ms warm | `SolverRouter.solve(stack_bb=67, ante='none', hand='AA', ...)` routes to `interpolated`, `meta['depths']=(60,80)`, strategy equals `0.65 * v60 + 0.35 * v80` componentwise (1e-9 tolerance). Enabled by **PR #173** + **PR #181**. |
| W5.3 | **PASS** (wiring; synthetic-fixture caveat) | ~1 s synthetic-fixture wall | `solve_postflop_from_blueprint(synthetic_blueprint, ..., board=Qs7h2d, ...)` returns a `BlueprintPostflopResult` with both stage walls populated (`wall_time_lookup_s`, `wall_time_solve_s > 0`), rust_vector backend, simplex-valid per-history strategies. Production-scale shipped-blueprint solve currently OOM-bound per `flop_subgame_perf_measurement_2026-05-28.md`; retarget post-v1.10 perf work. Enabled by **PR #177** + **PR #182** + **PR #181**. |
| W5.4 | **PASS** (new) | <1 ms (routing-decision only; no engine call) | `SolverRouter._decide_route` returns `custom_live_solve` when `range_override` is provided, even at exact blueprint depth (100 BB / no-ante). Locks the "blueprint cannot represent per-combo intensities; serving it would silently lose Wendy's custom edit" contract. Enabled by **PR #181** + **B10 Phase A/B/C** (PRs **#149** / **#154** / **#158**). |
| W5.5 | **PASS** (new) | <1 ms total (3 lookups warm) | `SolverRouter.solve(stack_bb=40, ante=<ante>, hand='72o', ...)` for each of `{'none','half','full'}` yields strategies differing pairwise by L1 > 0.05 (empirically: `72o` is fold-only at no-ante but call-100% at half/full ante per the 40 BB shards). Enabled by 27-shard bundle (chore `1783bef`) + **PR #174** (`normalize_ante`). |

---

## Caveats

- **W5.3 production-scale.** The wiring contract is met on a synthetic
  2-class blueprint; the shipped 169-class blueprint × full b300c line
  × flop subgame currently OOMs (per `flop_subgame_perf_measurement_2026-05-28.md`).
  v1.10 perf roadmap is the path to a production-scale W5.3.
- **Marcus's <100 ms tolerance threading Wendy.** W5.1's warm-cache
  budget is anchored to Marcus's "feels instant" threshold per
  `persona_time_budgets.md §1`. Wendy is an interactive consumer and
  her clock budget inherits Marcus's for interactive surfaces (the
  blueprint chart UI in PR #178 is the primary touchpoint).
- **W3.4 caveat carries forward.** Unchanged from the prior snapshot.

---

## Methodology

- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/feat-w5-persona-tests-premium-a`,
  branch `feat-w5-persona-tests-premium-a` off `origin/main` `b5aa023`.
- **Python:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python`
  (3.13.1, arm64).
- **Rust extension:** `poker_solver/_rust.cpython-313-darwin.so`
  copied from the main install (arm64 verified via `file`); W5.3 needs
  it for the postflop solve, W5.1/W5.2/W5.4/W5.5 do not.
- **Arch verification:** silent-skip hazard cleared per
  `feedback_dotso_arch_check`.
- **Blueprint asset:** shipped 27-shard bundle at `assets/blueprints/`
  (manifest schema v1.0, 9 depths × 3 antes; chore commit `1783bef`).
- **Test runner:** `pytest tests/test_w5_premium_a_personas.py -v` —
  13/13 PASS in 1.13 s.
- **Time budget:** sub-second for the 12 non-postflop tests; ~1 s for
  the W5.3 synthetic-fixture postflop solve. Well inside the 30-min
  per-persona kill-switch.

---

## References

- Prior snapshot: `docs/persona_status_2026-05-28-evening.md` (17/0/0/0)
- Audits driving this work: task #69 v1.9.0 audit; task #71 v1.10.0 audit
- Persona spec amendment: `docs/pr13_prep/persona_acceptance_spec.md` §"Wendy (Premium-A consumer)" + §"W5.1" through §"W5.5"
- Test file: `tests/test_w5_premium_a_personas.py` (13 tests)
- W5.1 PR: **PR #174** (`509f07d`) — BlueprintLoader, Phase 2 / #68
- W5.2 PRs: **PR #173** (`cb177c7`) — interpolation module, Phase 3 / #68; **PR #181** (`03842b0`) — solver router, Phase 5 / #68
- W5.3 PRs: **PR #177** (`18b9bcf`) — postflop subgame wiring, Phase 4 / #68; **PR #182** (`2aedb4b`) — b/r token normalization; **PR #181** (router dispatch)
- W5.4 PRs: **PR #181** (router); B10 Phase trail **PR #149** (`40ac87a`) / **PR #154** (`11e3f01`) / **PR #158** (`1839ee1`)
- W5.5 enablers: chore commit `1783bef` (27-shard bundle); **PR #174** (loader `normalize_ante`)
- W5.3 production-scale follow-up: `docs/flop_subgame_perf_measurement_2026-05-28.md`, `docs/v1_10_postflop_optimization_plan.md`
- Blueprint user guide: `docs/blueprint_user_guide.md`
- Blueprint developer guide: `docs/blueprint_developer_guide.md`
