# Persona Test Status Snapshot — 2026-05-28 (evening)

**Trigger:** PR #170 (W2.3 vector-form BR walk) merged. W2.3 reclassifies
PARTIAL → PASS now that the BR-walk wall time fits inside Sarah's 10-min gate.

**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/docs-persona-status-17-0-0-0`
(branch `docs/persona-status-17-0-0-0` off `origin/main` `caf90fb`).

**Prior snapshot:** `docs/persona_status_2026-05-28-late.md`:
**16 PASS / 1 PARTIAL / 0 BLOCKED / 0 FAIL** (W2.3 the lone PARTIAL).

---

## Bottom line

| Category | Count | Workflows |
|---|---|---|
| **PASS** | **17** | W1.1, W1.2, W1.3, W1.4, W1.5, W2.1, W2.2, **W2.3** (↑ via PR #170), W2.4, W2.5, W3.1, W3.2, W3.3, W3.4 (caveated), W3.5, W4.1, W4.2, W4.3 |
| **PARTIAL** | **0** | — |
| **BLOCKED** | **0** | — |
| **FAIL** | **0** | — |

**Net delta vs prior snapshot (`persona_status_2026-05-28-late.md`):** PASS 16→**17** (+1, W2.3), PARTIAL 1→**0** (-1, W2.3), BLOCKED 0→0 (=), FAIL 0→0 (=). Scope total = 17.

**Single reclassification this snapshot:**

| Workflow | Prior | Now | PR / driver |
|---|---|---|---|
| **W2.3** Sarah deep-stack turn KK vs c-bet | **PARTIAL** | **PASS** | **PR #170** (`188489b`) — opt-in vector-form BR walk; W2.3 fixture wall time **25.18 s** (well inside Sarah's 10-min / 600 s gate) |

No other persona workflow was retested in this snapshot; W1.x / W2.1 / W2.2 /
W2.4 / W2.5 / W3.x / W4.x verdicts carry forward unchanged from
`docs/persona_status_2026-05-28-late.md` per the constraint that only
empirically-backed verdicts move.

---

## W2.3 reclassification — PARTIAL → PASS

**Driver PR:** **PR #170** (`188489b`) — `feat(engine): vector-form BR walk
(W2.3 strict-PASS, opt-in)`. Merged 2026-05-28 08:14 UTC.

**Fixture:** Turn `Qs 7h 2d 5c`, 200 BB stacks, KK-vs-c-bet-range. Same
fixture shape as the prior `persona_status_2026-05-28-late.md` W2.3 retest
(which the BR walk had killed at ~11 min wall on a 3-class iter=10 attempt).

**Spec criteria** (`docs/pr13_prep/persona_acceptance_spec.md` line 45):
> Flop subgame with custom starting ranges; 5–15 min on standard flop, Rust tier.

**Sarah's session-budget gate:** ≤ 10 min (600 s) end-to-end.

**Empirical result (post-PR-170):**

| Metric | Value | Pre-PR-170 (late snapshot) |
|---|---|---|
| W2.3 fixture wall time | **25.18 s** | killed at ~11 min wall (BR walk dominated) |
| Sarah 10-min gate | **PASS** (25.18 s ≪ 600 s) | FAIL (>600 s) |
| Surface | `compute_exploitability_and_value_with_mode(BrWalkMode::Vector)` (new in PR #170) | per-combo BR walk (default; still public default post-PR-170) |

The vector-form path inverts the BR walk's loop order from
`(for combo: for node:)` to `(for node: for combo:)`, operating on a
length-`N_combos` f64 buffer in tight contiguous inner loops that LLVM
autovectorizes to NEON / AVX2 / SSE2 (the same pattern PR #114 used for the
forward DCFR walk). Per-combo BR walk remains the public default; vector is
opt-in via the new `BrWalkMode::Vector` enum. Default flip is deferred to
v1.10+ per the PR #170 task brief's broader-exposure constraint.

**Diff-test correctness:** PR #170 ships 10 diff-test fixtures
(`crates/cfr_core/src/exploit.rs`) covering river chance-enum,
turn chance-enum, the W2.3-shaped fixture, adversarial fixtures, and a
NO-OP fixed-combo case. All pass within 1e-9 of the per-combo baseline.

**Reclassification: PARTIAL → PASS.** Sarah's 10-min gate is met
empirically; W2.3 was the only PARTIAL on the late snapshot, so the
snapshot total reaches 17/0/0/0.

---

## Delta vs prior snapshot

**Prior snapshot:** `docs/persona_status_2026-05-28-late.md`
(post-5-PR-merge wave + B10 Phase D).

**What changed between the two snapshots:**

| # | Change | Driver |
|---|---|---|
| 1 | W2.3 PARTIAL → PASS | **PR #170** (`188489b`) vector-form BR walk |

**What did NOT change:**

- **W1.x (Marcus, 5/5 PASS):** No PRs in this interval touched the Marcus surface (CLI, default-action menu, simple HU 100 BB preflop subgame). Verdicts carry forward from `persona_status_2026-05-28-late.md` unchanged.
- **W2.1, W2.2, W2.4, W2.5 (Sarah, 4/5 PASS on the late snapshot):** No PRs touched W2.1 (full-tree preflop RvR; last moved by PR #122), W2.2 (per-combo `Range.diff`; last moved by B10 Phase A/B/C — PRs #149/#154/#158), W2.4, or W2.5. Verdicts carry forward unchanged.
- **W3.x (Daniel, 5/5 PASS) and W4.x (Priya, 3/3 PASS):** No PRs in this interval touched Daniel or Priya surfaces. Verdicts carry forward unchanged.

**PRs merged between the two snapshots (per `git log origin/main` since the late snapshot's `1839ee1` base):**

| PR | Commit | Subject | Persona impact |
|---|---|---|---|
| **#170** | `188489b` | vector-form BR walk (W2.3 strict-PASS, opt-in) | **W2.3 PARTIAL → PASS** |
| #176 | `44beb72` | blueprint user + dev guides (Phase 8, #68) | none — docs only |
| #177 | `18b9bcf` | postflop subgame wiring + range expansion (Phase 4, #68) | none — downstream blueprint surface |
| (ledger) | `92684b3` | rust optimization ledger with empirical speedups | none — docs only |
| #178 | `5df601b` | wire blueprint into chart widget + chained tab (Phase 6, #68) | none — downstream UI surface |
| #179 | `37a3d40` | J7o 40 BB walkthrough Tests 1-4 | none — docs only |
| #180 | `8bfa00c` | clippy lints in preflop_rvr_profile (CI rust lane) | none — CI only |
| #181 | `03842b0` | top-level solver router (Phase 5, #68) | none — downstream blueprint surface |
| #182 | `2aedb4b` | normalize b/r token equivalence at preflop boundary | none — preflop blueprint correctness fix |
| #183 | `caf90fb` | J7o player-POV walkthrough with postflop solves | none — docs only |

Only **PR #170** changed a persona verdict in this interval. The Phase 4-8
blueprint PRs (#176/#177/#178/#181/#182) are downstream of persona surfaces
that already PASS without the blueprint path and are not on Sarah's W2.3
critical path; they may move the user experience but do not change the
17-row persona table.

---

## Per-workflow table

### Marcus (W1.x) — 5/5 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28-late.md`.

### Sarah (W2.x) — 5/5 PASS *(W2.3 PARTIAL → PASS via PR #170)*

| ID | Verdict | Wall | Assertion |
|---|---|---|---|
| W2.1 | PASS | 258.00 s | `_rust.solve_hunl_preflop_rvr` (PR #122) — carries forward unchanged |
| W2.2 | PASS | 0.15 ms | Per-combo `Range.diff` via B10 Phase A/B/C (PRs #149/#154/#158) — carries forward unchanged |
| W2.3 | **PASS** ↑ from PARTIAL | **25.18 s** | **PR #170** (`188489b`) — vector-form BR walk; W2.3 fixture inside Sarah's 10-min gate |
| W2.4 | PASS | 2.01 s | PR #133 unblocker — carries forward unchanged |
| W2.5 | PASS | 12.17 s | Carries forward unchanged |

### Daniel (W3.x) — 5/5 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28-late.md`.

### Priya (W4.x) — 3/3 PASS *(no movement)*

Unchanged from `persona_status_2026-05-28-late.md`.

---

## Caveats

- **W3.4 caveat carries forward.** The "(caveated)" tag on W3.4 in the
  bottom-line table reflects the prior late-snapshot framing; no PR in this
  interval changed the W3.4 surface or the caveat scope.
- **Vector BR walk is opt-in.** `compute_exploitability_and_value` (the
  default public API called by `_rust.compute_exploitability`) still uses
  `BrWalkMode::PerCombo`. The W2.3 PASS evidence is on the
  `BrWalkMode::Vector` path; the default-flip is deferred to v1.10+ per
  PR #170 task brief. Persona-level retesters running the *default* path
  will still hit the prior PARTIAL wall time. The strict-PASS claim is
  contingent on opting into vector mode.
- **Perf gate < 10x.** PR #170's task brief asked for ≥10× speedup; measured
  is ~6.3× (per_combo 202 s vs vector 32 s on the W2.3-shaped fixture on
  M4 Pro arm64, per PR #170 body). The 6.3× win is sufficient to clear
  Sarah's 10-min gate (25.18 s W2.3 fixture wall), but the project-level
  10× claim was not met. The perf-gate test
  (`vector_perf_w2_3_at_least_10x`) is `#[ignore]`-gated and fails by
  design, surfacing the empirical reality.

---

## Methodology

- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/docs-persona-status-17-0-0-0`, branch `docs/persona-status-17-0-0-0` off `origin/main` `caf90fb`.
- **Python:** `/Users/ashen/Desktop/poker_solver/.venv/bin/python` (3.13, arm64).
- **W2.3 retest surface:** `compute_exploitability_and_value_with_mode(..., BrWalkMode::Vector)` (new in PR #170).
- **W2.3 empirical wall time:** **25.18 s** on the W2.3 fixture (Qs 7h 2d 5c, 200 BB, KK-vs-c-bet-range) — well inside Sarah's 10-min (600 s) gate.
- **Other persona verdicts:** carry forward unchanged from `persona_status_2026-05-28-late.md` per the "don't claim PASSes that aren't backed by data" rule. No new empirical retest was performed for W1.x / W2.1 / W2.2 / W2.4 / W2.5 / W3.x / W4.x in this snapshot.

---

## References

- Prior snapshot: `docs/persona_status_2026-05-28-late.md` (16/1/0/0)
- W2.3 PR: **PR #170** (`188489b`) — vector-form BR walk (W2.3 strict-PASS, opt-in)
- W2.3 vector test-fixture matrix: `docs/w2_3_vector_br_walk_test_fixtures.md`
- Persona spec: `docs/pr13_prep/persona_acceptance_spec.md`
- Prior W2.3 PARTIAL retest detail: `docs/persona_status_2026-05-28-late.md` §"W2.3 retest — PARTIAL"
- W2.3 archived BLOCKED doc (pre-PR-139): `docs/_archive_2026-05-26/persona_w2_3_retest_2026-05-26.md`
- Rust optimization ledger: `docs/rust_optimization_ledger.md` (empirical PR #114–#171 speedups)
</content>
</invoke>