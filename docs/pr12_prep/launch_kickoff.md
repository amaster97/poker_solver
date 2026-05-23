# PR 12 launch kickoff — 3-handed postflop stretch (POST-v1, explicitly approximate)

**Status:** PRE-STAGED PLAYBOOK. **Stretch goal, post-v1.** Do NOT execute until the entire v1 milestone (PR 1–11) has landed on `main` (not `integration`) and the user has approved firing PR 12. This kickoff can sit idle for months or years; PR 12 ships only when the user says go.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when v1 is shipped on `main` and PR 12 is approved to fire. PR 12 is the **largest single PR in the entire roadmap** (6–12 weeks; 2–3× the next-largest) and the only PR that ships an explicitly approximate solution concept.

**Branch:** `pr-12-three-handed-stretch` (`-stretch` suffix signals post-v1 status).

**Tone:** stretch goal. Honest about what we don't know — multi-player CFR has no Nash convergence proof (Gibson 2013 gives only iteratively-strict-dominated-action elimination), there is no external solver oracle without paid software (MonkerSolver), and the "≈ approximate equilibrium" framing is load-bearing on every output surface. Nothing here is a ship-it pressure point.

**Inputs:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md` (960 lines)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/audit_prompt.md`
- Launch-readiness: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/launch_readiness.md` (READY-WITH-PATCHES; 10/10 PASS; three minor)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`
- Theory anchors: `references/papers/pluribus_brown_2019_science.pdf` (p. 1–3 framing; p. 3 LCFR recipe), `references/papers/gibson_2013_regret_minimization.pdf` (IDSD)

---

## 1. Pre-flight gate (run BEFORE branch creation)

PR 12 gates against `main` (the v1 milestone branch), NOT `integration`. All seven checks must pass; no time pressure here.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. v1 is shipped on main: ALL of PR 1–11 merged AND tagged.
git fetch origin
git log --oneline main -20
# Expected: PR 1 through PR 11 all visible as merges; latest tagged release is the v1 tag.

# 1b. main tip matches origin/main (zero divergence).
git rev-parse main; git rev-parse origin/main
# Both hashes must be equal.

# 1c. PR 5 (HUNL postflop solver) AND PR 11 (library) confirmed on main.
git log --oneline main | grep -E 'PR 5|PR 11'
# PR 12 builds on PR 5's solver pattern + PR 11's SpotDescription serialization.

# 1d. Working tree clean.
git status

# 1e. All PR 12 prompts up to date.
ls -la docs/pr12_prep/
# pr12_spec.md (~960), agent_{a,b,c}_prompt.md, audit_prompt.md, launch_readiness.md.

# 1f. Pluribus + Gibson papers present.
ls references/papers/pluribus_brown_2019_science.pdf references/papers/gibson_2013_regret_minimization.pdf

# 1g. Reflog backup.
git rev-parse main > /tmp/main_pre_pr_12.hash
```

Optional sanity: `pytest -x -q` from `main` tip — fully green before branching. Also: `python -c "from poker_solver.hunl import HUNLConfig; c = HUNLConfig(); print(c.num_players, type(c.folded))"` — confirms the state of the existing `num_players` stub at `hunl.py:223`. Per `launch_readiness.md` Finding 2, this field already exists but `folded`/`all_in` are still 2-tuples; Agent A reconciles whether the field is wired through or just declared. This reconciliation is load-bearing for the whole PR.

---

## 2. Branch creation

Branched from `main` (not `integration`); PR 12 is post-v1 and merges back through integration → main on completion.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout main
git pull --ff-only origin main
git checkout -b pr-12-three-handed-stretch
git log --oneline -1  # expect: v1 milestone tip on main
```

---

## 3. Three-agent fan-out (staged by default for PR 12)

Per `pr_launch_runbook.md` §"Step 2", the three implementation agents normally launch in the SAME wave. **PR 12 has a wrinkle:** `HUNLConfig.num_players` already exists but `folded`/`all_in` are still 2-tuples (`launch_readiness.md` Finding 2). Agent A must reconcile this seam before B/C can safely consume the API.

**Pattern A (single-wave):** A/B/C fire in parallel after Agent A's 30-min reconciliation pass confirms the existing field is a clean stub.

**Pattern B (staged: A first, then B+C):** Agent A fires alone; wait for landing + regression-clean; then B and C in parallel. Slower wallclock; lower interface-drift risk.

**Default: Pattern B (staged).** PR 12 has the highest stakes-per-unit-of-work in the roadmap; time is not an issue (post-v1); the A↔B interface lock is load-bearing for the entire Rust port + solver.

For each agent, the prompt is the **full file body between the two `---` markers** — verbatim, no paraphrasing.

```
Wave 1 — Agent A alone:
  description: "PR 12 Agent A — N-player game-state generalization + side-pot helper + 3p invariant tests"
  prompt: <full body of docs/pr12_prep/agent_a_prompt.md between `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Wait for Agent A landing + `pytest -x` regression-clean on N=2 path.

Wave 2 — Agents B and C in parallel:
  description: "PR 12 Agent B — multiway_solver.py + multiway.rs + solver.py routing"
  description: "PR 12 Agent C — tests + fixtures + UI badge + CLI flag + Monker harness"
```

**Ownership recap:**

| Agent | Owns | Forbidden |
|---|---|---|
| A | `poker_solver/hunl.py`, `action_abstraction.py`, `tests/test_3p_core.py` | `multiway_solver.py`, `solver.py`, Rust, UI, any other test |
| B | `multiway_solver.py`, `crates/cfr_core/src/multiway.rs`, `solver.py` (routing branch), `__init__.py` (re-exports) | `hunl.py`, `action_abstraction.py`, tests, UI, `cli.py` |
| C | `tests/test_3p_solve.py`, `test_3p_diff.py`, `fixtures/multiway_fixtures.py`, all `ui/views/*.py`, `cli.py` | `hunl.py`, `multiway_solver.py`, `solver.py`, Rust, `test_3p_core.py` |

**Strong recommendation: split into PR 12 + PR 12.5** (per spec §12 #4). Given 6–12 week estimate and load-bearing A↔B interface:
- **PR 12 = Agent A only.** Game state generalized, side-pots, regression preserved. ~1.5–3 weeks. Low risk.
- **PR 12.5 = Agents B + C.** Solver, Rust port, UI, MonkerSolver harness. ~4–9 weeks. Builds on PR 12's stable interface.

Halves single-PR risk for the codebase's largest deliverable. **User makes the call before firing.** Default if user silent: split.

**Parallel fan-out during agent runtime** (no orchestrator idle):
- Doc inventory sweep across post-v1 surface; continuous pruning.
- Spec polish for PR 13+ candidates (real-time depth-limited search; 3p preflop; ICM-aware).
- `docs/autonomous_log.md` housekeeping.

---

## 4. Monitor + reconciliation patterns (PR 12-specific)

### 4a. Agent A — `num_players` field reconciliation drift
**Symptom:** existing field is wired into more places than the launch-readiness sweep caught (PR 9 preflop, PR 10 UI).
**Diagnosis:** read Agent A's note. If existing semantics conflict with §4.1 generalization, that's a spec ambiguity — **stop and escalate to user**, don't autonomously resolve.

### 4b. Cargo build errors on `multiway.rs`
**Common causes:** `arrayvec`/`smallvec` missing; `Game` trait bounds in `dcfr.rs` not generalizing from `[f32; 2]` to `Vec<f32>`/`SmallVec<[f32; 3]>`; LCFR weight integer-division bug if `iteration: usize` (should cast to `f32`).
**Diagnosis:** spec §3.2 + agent_b_prompt.md §4 are canonical.

### 4c. String-literal audit failure (HARD GATE)
**Symptom:** `grep -ri 'exploitability\|nash\|GTO' ... | grep -v 'best-response\|approximate\|≈\|near-Nash'` returns bare matches.
**Common causes:** Agent B used `exploitability` as a field name (must-fix; rename to `br_gap`); docstring "Nash convergence" without "no" qualifier; comment cites 2p0s exploitability theorem without "≈" guard.
**Diagnosis:** spec §3.4 + §9 #4 + audit_prompt.md focus areas 2+4 are canonical. Grep is the gate.

### 4d. Side-pot math fixture failures (most likely bug class)
**Diagnostic ladder — do NOT skip earlier rungs:**
1. Equal-stack all-in `[50,50,50]` → one main pot of 150. Most basic.
2. Unequal-stack all-in `[50,100,150]` → main 150 + side 100 + P2 returns 50. The "returns 50" piece lives in `utility`/payout, not in `_compute_side_pots` per se.
3. Folded-player case `[50,30(folded),100]` → folded's 30 to main; eligible = {0,2}. Most public bugs (Pio, postflop-solver, Slumbot) live here.
4. Tie at showdown — split with remainder by position (SB first postflop).
5. Odd-chip floor/ceiling — deterministic against TDA rule examples (Agent A's code comment citation).

**Anti-pattern (audit catches):** silently changing the helper to make a test pass. Spec §9 #1 + risk §10.3 + audit focus 3 all converge: TDA fixtures are load-bearing.

### 4e. Per-pair BR walk uses individual (not joint) opponent strategy
**Symptom:** synthetic-tree test in `test_3p_joint_br_fixture` fails — BR walk matches BR-against-either-individual rather than BR-against-joint.
**Diagnosis:** spec §9 #3 + agent_b_prompt.md item 1. At opponent-decision nodes, the walk weights by `σ_p(I, a)` per the strategy of whichever opponent `p` acts; strategies are NOT collapsed to a single marginal.

### 4f. Differential test (Python ↔ Rust) tolerance miss
**Symptom:** `test_3p_diff_river_subgame` fails with L1 slightly above 1e-6 after 500 iter.
**Diagnostic ladder:**
1. HashMap iteration order (same as PR 6 §6c): switch regret store to `BTreeMap` or `ahash::AHashMap` with fixed seed under `#[cfg(test)]`.
2. LCFR cutoff off-by-one: `iteration < self.lcfr_cutoff` (strict inequality). One-iteration drift compounds.
3. Pruning RNG sequence: Python and Rust must consume RNG in the same order with same seed.
4. Only after 1–3: dump per-infoset L1, trace the divergent CFR step.

**Anti-pattern:** silently relaxing 1e-6. Spec §14 locks it — tight because the fixture is small.

### 4g. UI surface breakage from range-count assumptions
**Symptom:** Agent C reports PR 10's `RangeWithFreqs` or `cell_strategy_summary` is HU-locked.
**Per spec §10.6:** if refactor is non-trivial, **stop and flag**. Scope as PR 12.5. Do NOT silently refactor PR 10 internals.

---

## 5. Audit + commit pipeline

### 5a. Interface drift reconciliation
```sh
cargo build --release
pip install -e .
pytest tests/test_3p_core.py tests/test_3p_solve.py tests/test_3p_diff.py -xvs
cargo test --package cfr_core multiway
pytest -x   # full regression — PR 3-11 all still pass
```

Typical drift: `HUNLConfig` rename/generalization conflict (spec §4.2 is canonical); `ruff`/`black` formatting (auto-fix); `mypy --strict` on new `multiway_solver.py` (strictest surface in codebase).

After all fixes: `pytest -x` MUST be fully green before audit.

### 5b. Audit + check battery in parallel

```sh
sh scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently launch the audit agent with the full body of `docs/pr12_prep/audit_prompt.md`. Audit writes `docs/pr12_prep/audit_report.md`.

**PR 12-specific must-fix triggers** (per audit focus areas 1–16):
- Approximate badge missing or suppressible on any output surface (§6.3 + §9 #10).
- Bare "Nash" / "GTO" / "exploitability" in 3p code paths or test docstrings (§9 #4 grep gate).
- Side-pot math fails any of the 5 TDA fixtures (§9 #1).
- Per-pair BR mislabeled "exploitability" anywhere (field name, docstring, output).
- DCFR_{1.5, 0, 2} used instead of LCFR for 3-handed (§3.2 + §9 #7).
- `num_players >= 4` not rejected with clear `NotImplementedError` (§9 #5).
- 3-way showdown multi-winner logic wrong (§9 #2).
- Regression in N=2 path: any PR 3-11 test fails.
- License contamination from postflop-solver or TexasSolver (AGPL).
- MonkerSolver data bundled (license violation; §7.5 is opt-in only).

### 5c. Commit + push + merge

```sh
git add poker_solver/ crates/cfr_core/ tests/ ui/ docs/pr12_prep/audit_report.md
git status   # re-verify staged set is exactly PR 12 surface
git commit -m "PR 12: 3-handed postflop stretch (explicitly approximate equilibrium)" # full body in commit message; cites LCFR + Pluribus + Gibson + AGPL exclusion + Monker opt-in
git push -u origin pr-12-three-handed-stretch
```

**Merge target is `main` (via `integration` as staging area)** because PR 12 is post-v1:
```sh
git checkout integration && git merge --no-ff pr-12-three-handed-stretch -m "Integration: merge PR 12"
# After soak time on integration (recommend ≥1 week given PR 12's scope):
git checkout main && git merge --no-ff integration -m "Main: ship PR 12 (post-v1)"
```

`--no-ff` mandatory. Update PLAN.md §2 trajectory + `docs/autonomous_log.md` per `pr_launch_runbook.md` §"Step 10".

---

## 6. Failure modes + recovery (3-handed-specific)

### 6a. Multi-player CFR fails to converge or cycles
**Expected behavior, not a bug** (spec §3.1 #4 + §10.1). Recovery:
1. Acknowledge and badge (extra UI line "⚠ stability degraded"; spec §7.4 + §6.3). Strategy still served.
2. Increase iterations (1000 → 10000) — sometimes compresses cross-seed drift below 0.05.
3. Tune `lcfr_cutoff` empirically — record in autonomous log.
4. If `pairwise_max > 0.5`, the strategy may not be useful regardless of framing — flag to user, don't ship silently.

### 6b. Memory exceeds 16 GB at 128/64/32
**Estimate, not promise** (§10.2). Recovery:
1. Tighter tier: 64/32/16 (~3–5 GB) or 32/16/8 (~1–2 GB) via `precompute-abstraction --bucket-counts`.
2. Smaller subgame (river-only is smallest).
3. Rust tier only — Python tier has higher per-infoset overhead; document and route user to Rust exclusively for that fixture.

### 6c. MonkerSolver cross-validation disagrees significantly
**Expected within 0.10 L1** (§7.5; loose threshold because abstractions differ). If much larger: check JSON schema in `tests/fixtures/monker/README.md`; check bucket-count mismatch; log to autonomous and flag user. **Do NOT silently relax 0.10.** Two approximate solvers comparing notes; significant disagreement is research-grade information.

### 6d. PyO3 build issues (same as PR 6)
`mod multiway;` missing from `lib.rs`; `#[pyfunction]` signature drift; missing `arrayvec`. Read maturin trace; spec §6.1 + agent_b_prompt.md "Rust port discipline" are canonical.

### 6e. UI badge accidentally suppressible
**Symptom:** audit reports badge can be hidden via `is_approximate` flag.
**Fix:** hardcode trigger on `result.num_players >= 3`, NOT on `is_approximate`. The `is_approximate` field is for documentation/serialization, not runtime suppression. Add `test_badge_cannot_be_disabled_via_config`.

---

## 7. Orchestrator decisions BEFORE firing

The launch-readiness verdict is READY-WITH-PATCHES (10/10 PASS, three minor, no blockers). Two decisions remain:

1. **Split PR 12 into PR 12 + PR 12.5?** Default if user silent: **split**. PR 12 = Agent A (game state); PR 12.5 = Agents B + C (solver, Rust, UI). Halves single-PR risk on the codebase's largest deliverable.

2. **Pattern A (single-wave) vs Pattern B (staged: A first)?** Default if user silent: **Pattern B (staged)**. Agent A reconciles the `hunl.py:223` `num_players` stub before B/C consume the interface.

Locked defaults (override at firing time if user wants different):
- Abstraction tier: 128/64/32 (§12 #6; tighter than HUNL default).
- LCFR cutoff fraction: T // 2 (§12 #7; per Pluribus).
- MonkerSolver validation: opt-in only (§12 #3; user-supplied data).
- Stability seeds: 3 seeds (0, 1, 2) (§12 #9; soft assert L1 < 0.05).

---

## 8. Risks (PR 12-specific, top to bottom by likely impact)

None block firing; each shapes recovery patterns in §6.

### 8.1 Multi-player CFR has no Nash convergence proof — the framing IS the deliverable
Spec §3.4 (no Nash claims), §6.3 (unsuppressible badge), §9 #4 (string-literal audit), Agent B docstring citations of Gibson 2013 + Pluribus. Risk persists despite mitigations because user perception isn't fully controllable. Honest fallback: lean into "near-Nash blueprint" framing Pluribus established.

### 8.2 Side-pot math is the most likely bug class
Pio caught side-pot bugs for years; postflop-solver's `bunching.rs` is partly edge cases; Slumbot has public bug reports. PR 12 mitigates with 5 TDA-rule unit fixtures (§9 #1) and explicit audit focus (§15). Additional edge cases may exist beyond public-solver coverage. Recovery: 6d + extend fixtures as bugs surface; log in autonomous.

### 8.3 No external validation oracle without MonkerSolver license
**Unique to PR 12.** PR 3-11 all had at least one external reference (open_spiel, noambrown, postflop-solver, PioSolver). PR 12 has none unless user owns MonkerSolver. Internal-only paths: structural sanity (§7.2), stability diagnostic (§7.4), intuition gauntlet (§7.6). Honest acknowledgment: we cannot prove the solver correct on real spots without external data; do not pretend otherwise.

### 8.4 Memory at default 128/64/32 may not fit 16 GB
Estimate, not promise (§10.2). Three tier alternatives in §5.2; `MemoryProbe` aborts cleanly. If default tier consistently OOMs across fixtures, that's a spec amendment to defaults — not a PR 12 blocker.

### 8.5 Linear CFR may not be the right schedule for 3-handed
Pluribus validated LCFR at 6-player; 3-handed-specific tuning is open research (§10.7). Configurable `lcfr_cutoff`; stability diagnostic gives signal.

### 8.6 95%-pruning thresholds may need re-tuning
Pluribus's thresholds were tuned for 6p blueprint scales; our cents-integer abstraction and 33/75/100/150/200 + all-in menu may need different `prune_threshold` (§10.8). Configurable; A/B test in autonomous log.

### 8.7 PR 10 UI may assume HU range-count
Per spec §10.6, `RangeWithFreqs` and `cell_strategy_summary` are designed range-count-agnostic. If PR 10b actually locks HU assumptions, 3-up matrix display requires PR 12.5 UI refactor. Mitigated by Agent C flagging early.

### 8.8 6–12 week estimate may slip on the Rust port
Mechanical translation, but n-player generics in Rust can be subtler than HU. PR 12.5 split absorbs the risk cleanly — game state lands first, solver lands when ready.

---

**End of kickoff.** When PR 12 fires (post-v1, user-approved), this file is the executable transcript. If anything here conflicts with `docs/pr12_prep/pr12_spec.md`, the spec wins.
