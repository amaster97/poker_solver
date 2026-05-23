# PR 12 launch invocations — copy-paste ready (POST-v1 STRETCH)

**Status:** PRE-STAGED PLAYBOOK. **Stretch goal, post-v1.** Do NOT execute until the entire v1 milestone (PR 1-11) has landed on `main` (not `integration`), the v1 tag exists, AND the user has explicitly approved firing PR 12. This file can sit idle for months or years; PR 12 ships only when the user says go.

**Purpose:** mechanical operations sheet for firing PR 12 — paste blocks in order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/launch_kickoff.md`. Operational shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/fanout_ready.md`. Spec (wins on conflict): `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md` (960 lines).

PR 12 is the **largest single PR in the roadmap** (6-12 week estimate; 2-3× the next-largest) and the only PR that ships an explicitly approximate solution concept. No Nash convergence proof; no external solver oracle without paid MonkerSolver license. Honest framing IS the deliverable.

---

## 1. Pre-launch verification (run AFTER v1 ships on main + tag, BEFORE branch creation)

All seven checks must pass. No time pressure here — this gate exists to be deliberate.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. v1 milestone is shipped on main: ALL of PR 1-11 merged AND tagged.
git fetch origin --tags
git log --oneline main -20
# Expected: PR 1 through PR 11 all visible as merges; latest tagged release is the v1 tag.
git tag --list 'v1*'
# Expected: at least one v1 tag (e.g., v1.0.0). If empty: STOP — v1 has not shipped.

# 1b. main tip matches origin/main (zero divergence).
git rev-parse main; git rev-parse origin/main
# Both hashes must be equal. If divergent: git pull --ff-only origin main

# 1c. PR 5 (HUNL postflop solver) AND PR 11 (library) confirmed on main.
git log --oneline main | grep -E 'PR 5|PR 11'
# PR 12 builds on PR 5's solver pattern + PR 11's SpotDescription serialization.

# 1d. Branch pr-12-three-handed-stretch does NOT yet exist.
git branch --list pr-12-three-handed-stretch
# Expected: empty. If branch exists from a prior aborted launch, rename
# (`git branch -m pr-12-three-handed-stretch-prior`) before re-creating.

# 1e. Working tree clean.
git status   # expected: "nothing to commit, working tree clean"

# 1f. All PR 12 prompts up to date (7 files).
ls -la docs/pr12_prep/
# Expected: pr12_spec.md (~960), agent_{a,b,c}_prompt.md, audit_prompt.md,
#           launch_readiness.md, launch_kickoff.md, fanout_ready.md, launch_invocations.md.

# 1g. Pluribus + Gibson theory anchors present.
ls references/papers/pluribus_brown_2019_science.pdf references/papers/gibson_2013_regret_minimization.pdf

# 1h. Reflog backup hash.
git rev-parse main > /tmp/main_pre_pr_12.hash
echo "main tip pre-PR-12: $(cat /tmp/main_pre_pr_12.hash)"
```

Optional sanity: `pytest -x -q` from `main` tip — fully green before branching. Also: `python -c "from poker_solver.hunl import HUNLConfig; c = HUNLConfig(); print(c.num_players, type(c.folded))"` — confirms the existing `num_players` stub state at `hunl.py:223`. If `folded` is `tuple[bool, bool]`, Agent A's reconciliation is needed; if already generalized, escalate to user (spec ambiguity — per `launch_readiness.md` Finding 2).

---

## 2. Branch creation

Branched from `main` (NOT `integration`); PR 12 is post-v1 and re-enters via integration → main on completion. Branch name `pr-12-three-handed-stretch` (`-stretch` suffix signals post-v1 status) hard-coded — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout main
git pull --ff-only origin main
git checkout -b pr-12-three-handed-stretch
git status         # expect: clean tree on pr-12-three-handed-stretch
git log --oneline -1   # expect: v1 milestone tip on main
```

---

## 3. Orchestrator decisions BEFORE firing agents

Per `launch_kickoff.md` §7 + `fanout_ready.md` §3, two decisions remain (launch-readiness verdict is READY-WITH-PATCHES: 10/10 PASS, three minor, no blockers):

1. **Split PR 12 into PR 12 + PR 12.5?** Default if user silent: **SPLIT**. PR 12 = Agent A only (~1.5-3 weeks, low risk — game state generalized, side-pots, regression preserved). PR 12.5 = Agents B + C (~4-9 weeks, builds on PR 12's stable interface — solver, Rust port, UI, MonkerSolver harness). Halves single-PR risk on the codebase's largest deliverable.

2. **Pattern A (single-wave) vs Pattern B (staged: A first)?** Default if user silent: **PATTERN B (staged)**. Agent A reconciles the `hunl.py:223` `num_players` stub before B/C consume the interface. Pattern A override is legal if A's reconciliation confirms the existing field is a clean stub (no wiring through PR 9/10); saves ~1.5-3 weeks wall-clock but raises interface-drift risk.

**The orchestrator MUST surface these decisions to the user BEFORE firing.** Locked defaults if user approves but stays silent on overrides: abstraction tier 128/64/32 (spec §12 #6); LCFR cutoff fraction T//2 (spec §12 #7); MonkerSolver validation opt-in only (spec §12 #3); stability seeds (0, 1, 2) (spec §12 #9).

---

## 4. Three-agent fan-out — STAGED Pattern B (default)

Per `launch_kickoff.md` §3 + `fanout_ready.md` §3: A↔B interface is load-bearing for the entire Rust port + solver; time is not an issue (post-v1); the existing `num_players` stub requires reconciliation before B/C can safely consume the API.

### 4a. Wave 1 — Agent A alone (own tool-call wave)

```
Agent A — "PR 12 Agent A — N-player game-state generalization + side-pot helper + 3p invariant tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr12_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Gate to Wave 2 (all four must hold):**
1. Agent A commit landed on `pr-12-three-handed-stretch`.
2. `pytest -x` regression-clean on N=2 path (ALL PR 3-11 tests still pass).
3. `HUNLConfig` fields reconciled: `folded` / `all_in` are now N-tuples or `Sequence[bool]` of length `num_players`.
4. `tests/test_3p_core.py` green (Agent A's owned test file).

If split into PR 12 + PR 12.5 (per §3 decision 1): Wave 1 = PR 12. Stop here; ship Agent A as a standalone PR; fire Wave 2 only after PR 12 lands on main and user re-approves for PR 12.5.

### 4b. Wave 2 — Agents B + C in parallel (SAME tool-call wave, after Wave 1 gate)

```
Agent B — "PR 12 Agent B — multiway_solver.py + multiway.rs + solver.py routing"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr12_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 12 Agent C — tests + fixtures + UI badge + CLI flag + Monker harness"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr12_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Forbidden |
|---|---|---|
| A | `poker_solver/hunl.py`, `action_abstraction.py`, `tests/test_3p_core.py` | `multiway_solver.py`, `solver.py`, Rust, UI, any other test |
| B | `multiway_solver.py`, `crates/cfr_core/src/multiway.rs`, `solver.py` (routing branch), `__init__.py` (re-exports) | `hunl.py`, `action_abstraction.py`, tests, UI, `cli.py` |
| C | `tests/test_3p_solve.py`, `test_3p_diff.py`, `fixtures/multiway_fixtures.py`, all `ui/views/*.py`, `cli.py` | `hunl.py`, `multiway_solver.py`, `solver.py`, Rust, `test_3p_core.py` |

**Parallel fan-out during agent runtime** (per parallel-agents-default + min-five-agents memory rules; no orchestrator idle): doc inventory sweep across post-v1 surface; PR 13+ spec polish (real-time depth-limited search; 3p preflop; ICM-aware); `docs/autonomous_log.md` housekeeping; continuous-pruning sweep. Aggregate per wave.

---

## 5. Expected wall-clock: 6-12 weeks (largest in roadmap)

Per spec §11 + `fanout_ready.md` §4. Staged Pattern B:
- Wave 1 (Agent A): ~1.5-3 weeks.
- Wave 2 (Agents B + C concurrent): ~4-9 weeks.
- Audit + bugfix cycle: ~0.5-1 week.
- MonkerSolver cross-validation (if user has data): ~0.5-1 week.
- Empirical abstraction tuning (memory profiler runs): ~0.5-1 week.

**Total: 6-12 weeks** end-to-end. If split into PR 12 + PR 12.5: PR 12 ships first as standalone milestone (~1.5-3 weeks); PR 12.5 absorbs the long tail (~4-9 weeks).

**Deliverables (PR surface):**
- `poker_solver/hunl.py` — N-player game state (`folded` / `all_in` become N-tuples; `_compute_side_pots` helper)
- `poker_solver/action_abstraction.py` — N-player legal action enumeration
- `poker_solver/multiway_solver.py` (~500 LOC) — LCFR (NOT DCFR) + 95%-pruning; per-pair BR walks (joint opponent strategy)
- `crates/cfr_core/src/multiway.rs` (~600 LOC) — Rust port; `Game` trait bounds generalized from `[f32; 2]` to `SmallVec<[f32; 3]>`
- `poker_solver/solver.py` — N-player routing branch (HUNL → existing; 3p → multiway; 4+ → `NotImplementedError`)
- `tests/test_3p_core.py` (Agent A, ~15 tests) + `test_3p_solve.py` (Agent C, ~10 tests) + `test_3p_diff.py` (Agent C, ~3 tests) + `fixtures/multiway_fixtures.py`
- `ui/views/*.py` — unsuppressible "≈ approximate equilibrium" badge (hardcoded on `result.num_players >= 3`)
- `cli.py` — `--num-players` flag + Monker harness (opt-in only, user-supplied data)

---

## 6. PR-12-specific risk reminders

Per `launch_kickoff.md` §4 + §8 + spec §10. Top three by likely impact (full ladder in kickoff):

1. **String-literal audit (HARD GATE).** Most common Agent B violation: `exploitability` as a field name (must rename to `br_gap`); docstring "Nash convergence" without "no" qualifier; comment cites 2p0s theorem without "≈" guard. Audit grep is the gate:
   ```sh
   grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ | grep -v 'best-response\|approximate\|≈\|near-Nash'
   # Expected: zero output. Any bare match = must-fix.
   ```

2. **Side-pot math (most likely bug class).** Pio caught side-pot bugs for years; postflop-solver and Slumbot have public bug reports. Diagnostic ladder — do NOT skip earlier rungs (kickoff §4d, spec §9 #1):
   - Equal-stack all-in `[50,50,50]` → one main pot of 150.
   - Unequal-stack all-in `[50,100,150]` → main 150 + side 100 + P2 returns 50.
   - Folded-player case `[50,30(folded),100]` → folded's 30 to main; eligible = {0,2}.
   - Tie at showdown — split with remainder by position (SB first postflop).
   - Odd-chip floor/ceiling — deterministic against TDA rule examples.
   **Anti-pattern (audit catches):** silently changing the helper to make a test pass.

3. **Multi-player CFR has no Nash convergence proof — the framing IS the deliverable.** Spec §3.4 (no Nash claims), §6.3 (unsuppressible badge), §9 #4 (string-literal audit), Agent B docstring citations of Gibson 2013 + Pluribus. Recovery patterns in kickoff §6a if convergence fails or cycles (acknowledge + badge + increase iterations + tune `lcfr_cutoff` empirically). If `pairwise_max > 0.5`, strategy may not be useful — flag user, do NOT ship silently.

Auxiliary risks worth tracking (kickoff §8.3-8.8):
- **No external validation oracle without MonkerSolver license** (unique to PR 12; PR 3-11 all had external references).
- **Memory at default 128/64/32 may not fit 16 GB** — three tier alternatives in spec §5.2; `MemoryProbe` aborts cleanly.
- **LCFR may not be the right schedule for 3-handed** — Pluribus validated at 6p; configurable `lcfr_cutoff`.
- **95%-pruning thresholds may need re-tuning** — Pluribus's thresholds were 6p NLHE; A/B test in autonomous log.
- **PR 10 UI may assume HU range-count** — per spec §10.6, if refactor non-trivial, stop and scope as PR 12.5.
- **Python ↔ Rust differential tolerance miss (1e-6 lock)** — kickoff §4f diagnostic ladder; do NOT silently relax.

---

## 7. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5a-5c. After Wave 2 returns (or after Wave 1 if PR 12 / PR 12.5 split):

```sh
cd /Users/ashen/Desktop/poker_solver

# 7a. Interface drift reconciliation (build + test the new surface).
cargo build --release
pip install -e .
pytest tests/test_3p_core.py tests/test_3p_solve.py tests/test_3p_diff.py -xvs
cargo test --package cfr_core multiway
pytest -x   # full regression — PR 3-11 all still pass (hard gate)

# Typical drift: `HUNLConfig` rename/generalization conflict (spec §4.2 is canonical);
# ruff/black formatting (auto-fix); `mypy --strict` on new `multiway_solver.py`
# (strictest surface in codebase). After all fixes: `pytest -x` MUST be fully green
# before audit.

# 7b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_12_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 12 audit — fresh reviewer, no implementation context (16 focus areas)"
#     prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr12_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr12_prep/audit_report.md.

# 7c. Commit (explicit paths only — no git add -A).
git status   # verify staged set is exactly PR 12 surface; no .env / secrets / Monker data blobs
git add poker_solver/ crates/cfr_core/ tests/ ui/ docs/pr12_prep/audit_report.md
git status   # re-verify
git commit -m "PR 12: 3-handed postflop stretch (explicitly approximate equilibrium)"
# Full commit message body cites LCFR + Pluribus + Gibson + AGPL exclusion + Monker opt-in;
# see launch_kickoff.md §5c.

# 7d. Push + --no-ff merge into integration (staging), then integration → main.
git push -u origin pr-12-three-handed-stretch
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-12-three-handed-stretch -m "Integration: merge PR 12"
git push origin integration

# Soak time on integration: recommend >=1 week given PR 12's scope.
# Only after soak time + user re-approves shipping to main:
git checkout main
git pull --ff-only origin main
git merge --no-ff integration -m "Main: ship PR 12 (post-v1)"
git push origin main

# 7e. Update PLAN.md §2 trajectory + docs/autonomous_log.md per plan-sync rule.
# Fire prune agent post-merge (continuous-pruning rule).
```

PR-12-specific must-fix triggers (hard stop; per kickoff §5b + audit focus 1-16): approximate badge missing or suppressible on any output surface; bare "Nash" / "GTO" / "exploitability" in 3p code paths or test docstrings; side-pot math fails any of the 5 TDA fixtures; per-pair BR mislabeled "exploitability" anywhere; DCFR_{1.5, 0, 2} used instead of LCFR for 3-handed; `num_players >= 4` not rejected with clear `NotImplementedError`; 3-way showdown multi-winner logic wrong; regression in N=2 path (any PR 3-11 test fails); license contamination from postflop-solver or TexasSolver (AGPL); MonkerSolver data bundled (license violation — opt-in only). `should-fix` / `nice-to-fix` can defer to follow-up. Full failure-mode + recovery in `launch_kickoff.md` §6a-6e.

---

## 8. Quick-reference paths

- Spec (wins on conflict): `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md` (960 lines)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/audit_prompt.md`
- Launch readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/launch_readiness.md` (READY-WITH-PATCHES; 10/10 PASS)
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/launch_kickoff.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/fanout_ready.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/launch_invocations.md`
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`
- Theory anchors: `references/papers/pluribus_brown_2019_science.pdf`, `references/papers/gibson_2013_regret_minimization.pdf`
- Check battery: `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh`
- Reflog backup: `/tmp/main_pre_pr_12.hash`
