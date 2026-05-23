# PR 12 fan-out ready — pre-staged launch sequence (POST-v1 STRETCH)

**Status:** PRE-STAGED. Do NOT execute until ALL of PR 1–11 has merged to `main` (not `integration`), v1 has been tagged, and the user has explicitly approved firing PR 12. This file can sit idle for months or years; PR 12 ships only when the user says go.

**Last verified:** 2026-05-22. Launch-readiness verdict READY-WITH-PATCHES (10/10 PASS, three minor, no blockers). `HUNLConfig.num_players` stub exists at `hunl.py:223` but `folded`/`all_in` are still 2-tuples — Agent A's reconciliation pass is load-bearing for the entire PR (per `launch_readiness.md` Finding 2).

This doc collapses `launch_kickoff.md` into the fire-when-v1-ships-and-user-approves order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/launch_kickoff.md`. Spec wins on conflict: `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md` (960 lines).

PR 12 is the **largest single PR in the roadmap** (6–12 week estimate; 2–3× the next-largest) and the only PR that ships an explicitly approximate solution concept. No Nash convergence proof; no external solver oracle without paid MonkerSolver license. Honest framing is the deliverable.

---

## 1. Pre-flight gate (run AFTER v1 ships on main, BEFORE branch creation)

All seven must pass. No time pressure here — this gate exists to be deliberate.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. v1 is shipped on main: ALL of PR 1–11 merged AND tagged.
git fetch origin
git log --oneline main -20
# Expected: PR 1 through PR 11 all visible as merges; latest tagged release is the v1 tag.

# 1b. main tip matches origin/main (zero divergence).
git rev-parse main; git rev-parse origin/main   # both hashes must be equal

# 1c. PR 5 (HUNL postflop solver) AND PR 11 (library) confirmed on main.
git log --oneline main | grep -E 'PR 5|PR 11'
# PR 12 builds on PR 5's solver pattern + PR 11's SpotDescription serialization.

# 1d. Working tree clean.
git status   # expect: "nothing to commit, working tree clean"

# 1e. All PR 12 prompts up to date (7 files).
ls -la docs/pr12_prep/
# Expected: pr12_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md, launch_readiness.md, launch_kickoff.md, fanout_ready.md.

# 1f. Pluribus + Gibson theory anchors present.
ls references/papers/pluribus_brown_2019_science.pdf references/papers/gibson_2013_regret_minimization.pdf

# 1g. Reflog backup.
git rev-parse main > /tmp/main_pre_pr_12.hash
```

Optional sanity: `pytest -x -q` from `main` tip — fully green before branching. Also: `python -c "from poker_solver.hunl import HUNLConfig; c = HUNLConfig(); print(c.num_players, type(c.folded))"` — confirms the existing `num_players` stub state. If `folded` is `tuple[bool, bool]`, Agent A's reconciliation is needed; if already generalized, escalate to user (spec ambiguity).

---

## 2. Branch creation

Branched from `main` (NOT `integration`); PR 12 is post-v1 and re-enters via integration → main on completion.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout main
git pull --ff-only origin main
git checkout -b pr-12-three-handed-stretch
git log --oneline -1   # expect: v1 milestone tip on main
```

Branch name hard-coded (`-stretch` suffix signals post-v1 status); do NOT improvise.

---

## 3. Three-agent fan-out — STAGED (Pattern B) by default

PR 12 is the only PR in the roadmap defaulting to a staged fan-out. Per kickoff §3: A↔B interface is load-bearing for the entire Rust port + solver; time is not an issue post-v1; the existing `num_players` stub at `hunl.py:223` requires reconciliation before B/C can safely consume the API.

**Pattern B default — Wave 1: Agent A alone.**

```
Wave 1 — Agent A alone:
  description: "PR 12 Agent A — N-player game-state generalization + side-pot helper + 3p invariant tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr12_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Gate to Wave 2:** Agent A lands (commit on branch), `pytest -x` regression-clean on N=2 path (all PR 3–11 tests still pass), `HUNLConfig` fields reconciled (`folded` / `all_in` are now N-tuples or `Sequence[bool]` of length `num_players`).

**Wave 2: Agents B + C in parallel (same tool-call block).**

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

**Pattern A (single-wave) override:** legal if Agent A's reconciliation pass confirms the existing field is already a clean stub (no wiring through PR 9/10). Wall-clock saves ~1.5–3 weeks but raises interface-drift risk. **User makes the call before firing.**

**Stronger recommendation: split PR 12 into PR 12 + PR 12.5** (per spec §12 #4 + kickoff §3). PR 12 = Agent A only (~1.5–3 weeks, low risk). PR 12.5 = Agents B + C (~4–9 weeks, builds on PR 12's stable interface). Halves single-PR risk on the codebase's largest deliverable. **Default if user silent: split.**

**Ownership lock (do NOT relax):**

| Agent | Owns | Forbidden |
|---|---|---|
| A | `poker_solver/hunl.py`, `action_abstraction.py`, `tests/test_3p_core.py` | `multiway_solver.py`, `solver.py`, Rust, UI, any other test |
| B | `multiway_solver.py`, `crates/cfr_core/src/multiway.rs`, `solver.py` (routing branch), `__init__.py` (re-exports) | `hunl.py`, `action_abstraction.py`, tests, UI, `cli.py` |
| C | `tests/test_3p_solve.py`, `test_3p_diff.py`, `fixtures/multiway_fixtures.py`, all `ui/views/*.py`, `cli.py` | `hunl.py`, `multiway_solver.py`, `solver.py`, Rust, `test_3p_core.py` |

**Parallel fan-out during agent runtime** (no orchestrator idle; min-five-agents floor): doc inventory sweep across post-v1 surface; PR 13+ spec polish (real-time depth-limited search; 3p preflop; ICM-aware); `docs/autonomous_log.md` housekeeping; continuous pruning.

---

## 4. Expected outputs + timeline

**Wall-clock:** 6–12 weeks total (largest in roadmap). Staged Pattern B: Wave 1 ~1.5–3 weeks; Wave 2 ~4–9 weeks concurrent on B + C. If split into PR 12 + PR 12.5: PR 12 ships first as standalone milestone.

**Deliverables (PR surface):**
- `poker_solver/hunl.py` — N-player game state (`folded` / `all_in` become N-tuples; `_compute_side_pots` helper)
- `poker_solver/action_abstraction.py` — N-player legal action enumeration
- `poker_solver/multiway_solver.py` — LCFR (NOT DCFR) + 95%-pruning; per-pair BR walks (joint opponent strategy)
- `crates/cfr_core/src/multiway.rs` — Rust port; `Game` trait bounds generalized from `[f32; 2]` to `SmallVec<[f32; 3]>`
- `poker_solver/solver.py` — N-player routing branch (HUNL → existing; 3p → multiway)
- `tests/test_3p_core.py` (Agent A) + `test_3p_solve.py` + `test_3p_diff.py` (Agent C) + `fixtures/multiway_fixtures.py`
- `ui/views/*.py` — unsuppressible "≈ approximate equilibrium" badge (hardcoded on `result.num_players >= 3`)
- `cli.py` — `--num-players` flag + Monker harness (opt-in only, user-supplied data)

**Pass criteria:** all PR 3–11 tests still pass (N=2 path regression-clean); `pytest tests/test_3p_*.py -xvs` green; `cargo test --package cfr_core multiway` green; `mypy --strict` on `multiway_solver.py` (strictest surface); string-literal grep gate passes (no bare "Nash" / "GTO" / "exploitability" in 3p code paths); side-pot math passes all 5 TDA fixtures; UI badge unsuppressible (`test_badge_cannot_be_disabled_via_config`).

---

## 5. Hard gates (string-literal audit + side-pot math)

**String-literal grep gate** (kickoff §4c, spec §3.4 + §9 #4):
```sh
grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ | grep -v 'best-response\|approximate\|≈\|near-Nash'
# Expected: zero output. Any bare match = must-fix.
```
Most common Agent B violation: `exploitability` as a field name (rename to `br_gap`). Docstring "Nash convergence" without "no" qualifier. Comment cites 2p0s theorem without "≈" guard.

**Side-pot math diagnostic ladder** (kickoff §4d, spec §9 #1 — most likely bug class):
1. Equal-stack all-in `[50,50,50]` → one main pot of 150.
2. Unequal-stack all-in `[50,100,150]` → main 150 + side 100 + P2 returns 50.
3. Folded-player case `[50,30(folded),100]` → folded's 30 to main; eligible = {0,2}.
4. Tie at showdown — split with remainder by position (SB first postflop).
5. Odd-chip floor/ceiling — deterministic against TDA rule examples.

**Anti-pattern (audit catches both):** silently changing the helper to make a test pass; silently relaxing the 1e-6 Python ↔ Rust differential tolerance.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5: after Wave 2 returns, run `cargo build --release` + `pip install -e .` + `pytest tests/test_3p_*.py -xvs` + `cargo test --package cfr_core multiway` + `pytest -x` (full regression). Then audit + check battery in parallel: `sh scripts/check_pr.sh > /tmp/check_pr_12_output.log 2>&1` + audit agent writes `docs/pr12_prep/audit_report.md` (full body of `audit_prompt.md`).

PR 12-specific must-fix triggers (kickoff §5b, audit focus 1–16): approximate badge missing or suppressible; bare "Nash" / "GTO" / "exploitability" in 3p code paths; side-pot math fails any of the 5 TDA fixtures; per-pair BR mislabeled "exploitability"; `DCFR_{1.5, 0, 2}` used instead of LCFR for 3-handed; `num_players >= 4` not rejected with clear `NotImplementedError`; 3-way showdown multi-winner logic wrong; N=2 regression; license contamination from postflop-solver / TexasSolver (AGPL); MonkerSolver data bundled (license violation; opt-in only).

**Merge target is `main` via `integration` as staging** (PR 12 is post-v1):
```sh
git checkout integration && git merge --no-ff pr-12-three-handed-stretch -m "Integration: merge PR 12"
# Soak time on integration: recommend >=1 week given PR 12's scope.
git checkout main && git merge --no-ff integration -m "Main: ship PR 12 (post-v1)"
```

`--no-ff` mandatory both hops. Update `PLAN.md` §2 trajectory + `docs/autonomous_log.md`. Fire prune agent post-merge (continuous-pruning rule).

Full pipeline lives in `launch_kickoff.md` §5a–5c + §6 failure-mode recovery. This doc stops at fan-out launch.
