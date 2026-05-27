# Gate 4 Operational Plan — 200K-iter Production-Scale HUNL Validation

**Status:** PRE-STAGED — awaiting user approval to execute.
**PLAN.md §10 Gate 4:** "≥1 200K-iter HUNL build run end-to-end on the v1 .dmg artifact; exploitability convergence curve recorded."
**Date staged:** 2026-05-23.
**Recommended scale:** 50K-iter scaled validation first (~2.5 hr); 200K (~10 hr) overnight follow-up if 50K clean.
**Recommended action:** USER-AUTHORIZE-50K-RUN.

---

## 1. Goal

- Run a production-scale HUNL postflop solve end-to-end on `origin/main @ 3843ce7` (v1.7.0 engine).
- Capture exploitability convergence curve (mbb/g per checkpointed iter).
- Validate Sarah-class time budgets at production scale (per `feedback_persona_time_budgets`).
- Resolve the §6 load-bearing caveat ("Production-scale 200K-iter HUNL validation … never run").

### Scaled options

| Scale | Iters | Expected wall-clock | Use case |
|---|---|---|---|
| Smoke | 20K | ~1 hr | First-pass sanity (use only if 50K projects to >3 hr) |
| **Recommended** | **50K** | **~2.5 hr** | **Initial validation; clean signon target** |
| Full Gate 4 | 200K | ~10 hr | Overnight follow-up once 50K clean |

Wall-clock projections extrapolated linearly from `docs/v1_7_0_nash_path_perf_profile.md` (river 8c × 500 iter = 3.77 s) and PR 6 ~24× speedup baseline; HUNL postflop is the `solve_hunl_postflop` path, not the Nash vector-form path, so these are heuristic — instrument and revisit per `feedback_no_extrapolate` after the first checkpoint.

---

## 2. Pre-flight checks

Run from `/Users/ashen/Desktop/poker_solver` BEFORE creating the worktree:

```bash
# (a) .so arch (per feedback_dotso_arch_check.md)
file poker_solver/_rust.cpython-*.so | grep arm64
# Local .so as of 2026-05-23: universal2 (arm64 + x86_64). PASS — but fresh
# worktree must rebuild via `maturin develop --release` and re-verify.

# (b) Disk space — 200K may produce 5-15 GB of intermediate state
df -h /tmp /Users/ashen/Desktop/poker_solver
# Need ≥20 GB free on the volume hosting the worktree.

# (c) No CPU-bound agents in flight (avoid contention with concurrent solver runs)
ps aux | grep -E "(python -m poker_solver|cargo|pytest)" | grep -v grep
# Expect empty. If anything else is mid-solve, wait or kill.

# (d) Memory headroom
vm_stat | head -5     # confirm >12 GB free pages on M-series (16 GB ceiling per §10)
```

If any check fails, STOP and surface to user before proceeding.

---

## 3. Fixture spec

**Rationale:** Use the existing `default_tiny_subgame()` River fixture (board `As 7c 2d Kh 5s`) as the SHAPE template, but parameterize to a FLOP start so the run actually exercises multi-street convergence. Pure river is too cheap to qualify as "production scale."

**Recommended fixture (flop start, lossless, full ranges via abstraction-attached default):**

```python
# Conceptual config — NOT a code change; this is what the CLI invocation
# produces via _build_postflop_config() in poker_solver/cli.py L98.
config = HUNLConfig(
    starting_stack=10_000,                  # 100 BB (1 BB = 100 chips)
    small_blind=50,
    big_blind=100,
    starting_street=Street.FLOP,
    initial_board=(As, 7c, 2d),             # PR 5 standard flop fixture
    initial_pot=200,                        # 2 BB
    initial_contributions=(100, 100),
    bet_size_fractions=(0.33, 0.75, 1.0, 1.5, 2.0),  # PR 3 locked decision
    # all-in always available regardless of bet_size_fractions
)
```

**Fixture parameters (per PR 3 locked decisions + PLAN.md):**
- Board: `As 7c 2d` (PR 5 standard flop; dry, ace-high, three-suit)
- Action menu: 33/75/100/150/200/AI (locked per PR 3, see PLAN.md L90)
- Stacks: 100 BB symmetric (default)
- Postflop cap: 3 raises per street (locked per PR 3)
- Ranges: full ranges (lossless on flop will WARN; that's expected for Gate 4 — production scale means stressing the lossless tree)

**Alternative (if 50K projects too long):** drop to `--abstraction` with PR 4 `256/128/64` bucket counts; this matches the PLAN.md card-abstraction commitment and makes the run an order of magnitude faster, but it's now an abstraction-tier validation, not lossless. Note clearly in the result doc which path was taken.

---

## 4. Execution command

```bash
# (1) Fresh worktree from origin/main @ 3843ce7 (avoid lock contention per
#     feedback_no_concurrent_branch_ops). The PID suffix dedupes if other
#     agents are spawning worktrees concurrently.
git -C /Users/ashen/Desktop/poker_solver worktree add /tmp/gate4-run-$$ origin/main
cd /tmp/gate4-run-$$

# (2) Rebuild Rust extension for host arch (universal2 .so from main is fine,
#     but build fresh in the worktree to guarantee no skew).
pip install -e .
maturin develop --release --manifest-path crates/poker_solver_rs/Cargo.toml
file poker_solver/_rust.cpython-*.so | grep arm64    # MUST return non-empty.

# (3) Verified CLI command (matches poker_solver/cli.py L631-731 `solve`
#     subparser; flags --hunl-mode postflop, --board, --stacks, --backend,
#     --iterations, --seed, --log-every all wired):
python -m poker_solver.cli solve \
    --game hunl \
    --hunl-mode postflop \
    --backend rust \
    --board "As 7c 2d" \
    --stacks 100 \
    --bet-sizes 33,75,100,150,200 \
    --iterations 50000 \
    --log-every 5000 \
    --max-memory-gb 14.0 \
    --seed 42 \
    | tee /tmp/gate4_50k_$$.log

# For 200K follow-up: --iterations 200000 --log-every 10000
```

**CLI verification:** the `solve` subparser is defined at `poker_solver/cli.py:631`; flags above all map to existing `argparse.add_argument` lines (L633-720). No code changes required. The Rust backend on the postflop path routes through `solve()` (cli.py:244-256) per PR 6 locked decision D10.

**Output capture:** the CLI prints game value, exploitability, average strategy, and per-street memory section (cli.py:280-302). `tee` to log captures both for later parsing.

---

## 5. Expected wall-clock

Heuristic extrapolation (instrument-and-revisit per `feedback_no_extrapolate`):

- **20K iter** (~1 hr): use only if 50K projects to >3 hr at first checkpoint.
- **50K iter** (~2.5 hr): RECOMMENDED initial scale. Marcus session budget = batch; Sarah budget = study tier; Priya budget = overnight tier — all comfortable.
- **200K iter** (~10 hr): overnight, full Gate 4 closeout.

Per `feedback_persona_time_budgets`, Gate 4 is a Priya batch / overnight workflow, NOT interactive. Marcus's <30 s budget does NOT apply.

After first `--log-every 5000` checkpoint fires (~15 min into 50K), update the extrapolation: if projected total >5 hr, kill and re-plan (smaller board, abstraction tier, or scaled-down iters).

---

## 6. Capture

The solver auto-snapshots when `--log-every N` is set. Capture should yield:

```
Iter checkpoints (50K run): 5K, 10K, 15K, 20K, 25K, 30K, 35K, 40K, 45K, 50K
Iter checkpoints (200K run): 10K, 20K, ..., 200K (20 checkpoints)
```

At each checkpoint, snapshot:
1. **Exploitability (mbb/g)** — from `result.exploitability_history[-1]` printed by cli.py:286.
2. **Wall-clock since start** — derived from `tee` log timestamps.
3. **Memory (per-street, total GB, RSS GB)** — from the Memory section (cli.py:301).

Post-run, capture:
4. **Final average strategy** — printed by cli.py:291-296; redirect to JSON via library export (next section).
5. **Final memory peak** — RSS GB from last checkpoint.

---

## 7. Acceptance criteria

Gate 4 passes when ALL of:

1. **Convergence:** exploitability monotonically non-increasing across checkpoints (with at most one transient up-tick per `feedback_label_vs_semantics` — verify with eyeball, not just min-fit).
2. **Memory:** `result.memory_report.total_gb ≤ 14.0` AND `process_rss_gb ≤ 16.0` (M-series MacBook ceiling per PLAN.md §10).
3. **Time:** completes within projected budget; >2× projected = STOP and diagnose, do NOT autocorrect (kill-switch per `feedback_persona_time_budgets`).
4. **Sanity (spot-check):** final average-strategy AA preflop bet-frequency ~100% on opens; tight ranges 3-bet stronger hands more often than weaker hands; no NaN/inf in any probability.
5. **No MemoryError, no panic, no abort.** A clean MemoryError with partial report (cli.py:271-278) is REJECTION, not pass.

If any fail → mark Gate 4 INCOMPLETE, file findings, do not advance to v-final .dmg.

---

## 8. Anti-patterns

Do NOT:
- Run on the shared working tree (`/Users/ashen/Desktop/poker_solver`) — use `/tmp/gate4-run-$$` worktree per `feedback_no_concurrent_branch_ops`.
- Run if another CPU-bound agent is in flight (per `feedback_min_five_agents` M-series cap ≤2-3 CPU-bound).
- Skip the `.so` arch check (silent test-skip stall pattern, `feedback_dotso_arch_check`).
- Trust a 50K wall-clock < projection without verifying iters actually completed (could be early-exit on `target_exploitability` — we don't pass that flag, so this should not happen, but verify).
- Extrapolate from a single checkpoint to the run (instrument-and-revisit per `feedback_no_extrapolate`).
- Auto-advance to 200K without showing 50K result to user.
- Commit the result JSON to git without sanitization audit per `feedback_public_repo_hygiene` (it's solver output, should be public-OK, but still audit).

---

## 9. Post-run output

Write three artifacts:

1. **`/Users/ashen/Desktop/poker_solver/docs/gate_4_50k_result.json`** (or `gate_4_200k_result.json`)
   - Schema: `library export` format (see `cli.py:_cmd_library_export`).
   - Generate via: `python -m poker_solver.cli library export <spot_id> docs/gate_4_50k_result.json` after `--game hunl` solve writes to the library.
   - Alternatively re-emit strategy + history directly from the tee log.

2. **`/Users/ashen/Desktop/poker_solver/docs/gate_4_validation_report.md`** — narrative covering:
   - Fixture (board, stacks, bet sizes, ranges).
   - Pre-flight check log.
   - Per-checkpoint table: iter / exploitability mbb/g / wall-clock / RSS GB.
   - Convergence curve (ASCII or PNG link).
   - Acceptance-criteria pass/fail line-by-line per §7.
   - Recommendation: GATE-4-PASS / GATE-4-PARTIAL / GATE-4-FAIL.

3. **Memory snapshot tracker** — embed in §2 of the report; per-street MB at each checkpoint.

Then update:
- `PLAN.md` §10 Gate 4 status from "pending" → final verdict.
- `PLAN.md` §6 load-bearing caveat — remove or downgrade to "resolved 2026-05-23 via Gate 4 50K run."
- `docs/comprehensive_review_2026-05-23-final.md` L269/L284/L317 — strike "blocked behind Gate 1."

---

## 10. Recommended scale

**USER-AUTHORIZE-50K-RUN** as the initial step.

Reasoning:
- "Several hours autonomous + clean signon" fits 2.5 hr 50K cleanly.
- Full 200K is overnight tier; better to confirm 50K convergence + memory before committing 10 hr.
- Per `feedback_research_first_failure_protocol`: instrument FIRST, then scale UP — not the inverse.
- 50K is already past the PR 5 reference (50K default per `_DEFAULT_ITERATIONS`); 200K is 4× that.

If 50K clean → schedule 200K as overnight follow-up the same evening (separate authorization).

---

## Cross-references

- `PLAN.md` §10 Gate 4 (L394), §6 load-bearing caveat (L301-303), §12 burst log (L430).
- `poker_solver/cli.py` `solve` subparser (L631-731).
- `poker_solver/hunl_solver.py` `solve_hunl_postflop` (L100-226).
- `poker_solver/hunl.py` `default_tiny_subgame` (L337).
- `docs/v1_7_0_nash_path_perf_profile.md` — perf scaling baseline.
- Memory: `feedback_dotso_arch_check`, `feedback_no_concurrent_branch_ops`, `feedback_persona_time_budgets`, `feedback_no_extrapolate`, `feedback_public_repo_hygiene`, `feedback_min_five_agents`.
