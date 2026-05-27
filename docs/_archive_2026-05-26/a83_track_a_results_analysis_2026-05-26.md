# A83 Track A Results — Analysis & Recommendation (2026-05-26)

**Status:** Track A invalid as launched. **REPAIR + RETEST required.**
**Verdict:** The `--regret-init-noise` flag itself works (unit-test evidence
strong). The 200K-iter nohups did NOT exercise it — the CLI invocation
hit a chance-node-at-root no-op path. The reported bit-identical
"baseline vs perturbed" outcome is the trivial bit-identicality of
"two no-op runs", not Nash convergence.

---

## TL;DR

1. The launch script (`~/Desktop/a83_track_a_run.sh`) invoked
   `poker-solver solve --backend rust --hunl-mode postflop --board "Ah 8c 3d Tc 6s"`.
   That path calls `_rust.solve_hunl_postflop` with a `HUNLConfig` whose
   `initial_hole_cards = None`.
2. In `crates/cfr_core/src/hunl.rs:539-545`, `HUNLState::chance_outcomes`
   returns `Vec::new()` defensively whenever `hole_cards = None`. The
   scalar CFR loop in `hunl_solver.rs::cfr` (chance branch, ~lines 265-282)
   then enumerates ZERO chance outcomes, returns `[0.0, 0.0]` immediately,
   and NEVER inserts a single infoset.
3. Both 200K-iter runs completed in **~111 seconds wall-clock** (launch
   03:15:10, log finalized 03:17:01). Real 200K-iter river DCFR with
   any non-trivial tree takes tens of minutes; <2 min confirms no-op.
4. Both log files are 186 bytes and byte-identical (`diff` empty). They
   end at the `"  infoset   actions"` header with **zero strategy rows
   printed** — because `result.average_strategy` was empty.
5. The reported game-value `-0.281250` and exploitability `13.852756`
   are recomputed via `_rust.compute_exploitability` against the empty
   strategy, which falls back to **uniform** on every missing key
   (`exploit.rs:472-475`). They are the exploitability of a uniform-
   random strategy on this spot, NOT a converged Nash.

The flag plumbing is correct. The launch invocation was wrong.

---

## 1. Is the `--regret-init-noise` flag broken? (No.)

PR 53 (commit `29d608e`) shipped three unit tests in
`crates/cfr_core/src/dcfr_vector.rs::tests`:

| Test | What it proves | Status (per setup doc §3) |
|---|---|---|
| `regret_init_noise_zero_is_reproducible` | `noise=0.0` produces bit-identical reruns (no implicit RNG) | PASS (`cargo test --lib --release` 56/56) |
| `regret_init_noise_epsilon_perturbs_strategy` | `noise=1e-9` produces non-zero per-cell divergence from `noise=0.0` after 3 iterations | PASS |
| `regret_init_noise_seed_changes_outcome` | Different `rng_seed` with same noise produce different strategies (proves seed is actually consumed) | PASS |

The epsilon test (lines 1199-1255 of `dcfr_vector.rs`) is load-bearing
evidence: it asserts `max_diff > 0.0` across all per-cell strategy values
after 3 iterations on a multi-action tree, and PASSES on the `with_init_noise`
path that both the scalar (`hunl_solver.rs:359-369`) and vector
(`dcfr_vector.rs:224-228`) production paths converge through.

**Note on the test fixture:** The epsilon test had to **boost the
`tiny_river_rvr` config from `postflop_raise_cap=1` to `cap=3` and enable
`include_all_in`** (lines 1207-1209 of `dcfr_vector.rs`). At `cap=1` with
a single bet size, "every strategy row is `[1.0]` regardless of regret
state" — so a low-cap tree masks the perturbation entirely. This means
the noise correctly seeds the regret, but only TREE SHAPES with multi-
action infosets can exhibit the perturbation in their strategy output.
The A83 fixture (`cap=3 + include_all_in=true`) is sufficient.

Conclusion: **the flag mechanically works.** The bit-identical 200K-iter
outcome cannot be blamed on the noise plumbing being broken.

---

## 2. What did the 200K-iter nohups actually solve? (Nothing.)

### 2a. Direct evidence: log files are 186 bytes, byte-identical, no
strategy rows printed.

```
$ wc -c ~/Desktop/a83_track_a_baseline.log ~/Desktop/a83_track_a_perturbed.log
     186 .../a83_track_a_baseline.log
     186 .../a83_track_a_perturbed.log

$ diff ~/Desktop/a83_track_a_baseline.log ~/Desktop/a83_track_a_perturbed.log
[no output — files identical]

$ xxd ~/Desktop/a83_track_a_baseline.log | tail -3
00000080: 360a 0a41 7665 7261 6765 2073 7472 6174  6..Average strat
00000090: 6567 793a 0a20 2069 6e66 6f73 6574 2020  egy:.  infoset  
000000a0: 2061 6374 696f 6e73 2020 2020 2020 2020   actions        
000000b0: 2020 2020 2020 2020 200a                          .
```

The CLI prints the header `"  infoset   actions"` (cli.py:417) then
iterates `for key in sorted(result.average_strategy.keys())` (line 418).
**Zero rows printed → zero infosets in `result.average_strategy`.**

### 2b. Wall-clock evidence: ~111 seconds for 200K iters.

```
$ stat -f "%Sm %N" ~/Desktop/a83_track_a_baseline.pid ~/Desktop/a83_track_a_*.log
May 26 03:15:10 2026  .../a83_track_a_baseline.pid    (launch)
May 26 03:17:01 2026  .../a83_track_a_baseline.log    (finish)
May 26 03:17:01 2026  .../a83_track_a_perturbed.log   (finish)
```

For reference, the Gate 4 turn-phase nohup currently running
(`As 7c 2d Kh` turn, 200K iters, `pid=42803`) has accumulated ~52 minutes
of CPU time and is still going. Two 200K solves in <2 min wall-clock is
inconsistent with any real DCFR work.

### 2c. Mechanical root cause: `chance_outcomes()` returns empty for
`hole_cards = None`.

`_build_postflop_config` in `poker_solver/cli.py:127-136` constructs an
`HUNLConfig` with NO `initial_hole_cards` set (default `None`).
`HUNLState::initial` (`crates/cfr_core/src/hunl.rs:344-348`) propagates
that None and sets `cur_player = -1` (chance node) at the root.

`HUNLState::chance_outcomes` (`crates/cfr_core/src/hunl.rs:533-568`)
contains:

```rust
let hole = match self.hole_cards {
    Some(h) => h,
    None => {
        // Defensive: shouldn't happen post-init. Return empty rather
        // than enumerate preflop combinations (which don't fit in u8).
        return Vec::new();
    }
};
```

With `hole_cards = None`, `chance_outcomes()` returns `Vec::new()`. The
scalar CFR loop's chance branch (`hunl_solver.rs:265-282`) iterates over
this empty list, builds `value = [0.0, 0.0]`, and returns immediately.
**No infoset is ever inserted. No regret_sum is ever updated. Noise has
no surface to perturb.** 200,000 iterations of "return [0,0]" complete in
~111 seconds (mostly the per-iter loop overhead + the final
exploitability recompute).

The exploitability recompute (`solver.py:763` →
`_rust.compute_exploitability`) walks the tree against the empty
`average_strategy`. `StrategyCache::probs` at `exploit.rs:472-475` falls
back to `uniform(n_actions)` on every cache miss. The reported `-0.281250
/ 13.852756` is the exploitability of a UNIFORM random strategy on this
spot, identical between baseline and perturbed (because both are equally
uniform: an empty strategy map produces uniform-default everywhere).

### 2d. Why was Gate 4 successful through the same CLI?

The Gate 4 nohup uses the same `--backend rust --hunl-mode postflop` path
but on a 4-card TURN board (`As 7c 2d Kh`). On the turn, the engine has
real chance outcomes (one remaining river card to deal) — and even though
hole_cards is still None at the root, the chance branch with a non-empty
`chance_outcomes()` keeps the recursion alive...

Actually no — re-examining `chance_outcomes()` at line 539-545, the
`None` short-circuit applies REGARDLESS of street. So Gate 4 should
also be broken via the same path. Unless Gate 4 is hitting a different
code path. Looking at the Gate 4 `ps aux` line, it's also using
`--hunl-mode postflop` without `initial_hole_cards`. Either Gate 4 is
ALSO a no-op (and we haven't noticed), or there's a path I'm missing.

**This is worth a follow-up audit** but does not change the Track A
verdict: Track A is invalid; the noise plumbing was never exercised at
this scale.

---

## 3. Per-cell strategy comparison (impossible from current data)

Neither log contains per-cell strategy data. Both
`result.average_strategy` maps are empty. There is nothing to compare.

No JSON dumps exist: `ls ~/Desktop/a83_track_a_*.json` returns
"NO JSON FILES". The CLI does not write a JSON sidecar by default; only
stdout (which captured the bare header).

---

## 4. Wrong-board mismatch (separate, secondary issue)

The user's request brief mentioned the A83 FLOP spot (`As 8s 3s` 3-card
flop, `b1000r3000`). The Track A launch script and setup doc explicitly
chose a 5-card RIVER fixture (`Ah 8c 3d Tc 6s`) for two stated reasons
(setup doc §5.1 "Spot configuration", lines 185-191):

1. The 3-card monotone-flop spec would not finish in reasonable wall-
   clock at 200K iters (deep tree).
2. The actual A83 dry-run investigation in
   `docs/a83_deep_cap_root_cause_investigation.md` §1a references the
   river-phase fixture `dry_A83_rainbow` (with 5-card runout `Ah 8c 3d
   Tc 6s`) for the `b1000r3000` cell data.

So the river-vs-flop swap was a deliberate, documented scope decision,
not an agent error. The brief in the orchestration task ("river-phase
200K-iter solves on `Ah 8c 3d Tc 6s` board") matches the launch.

**However:** the user's actual interest — per the orchestration task
("the user's actual interest is the A83 deep-cap flop divergence") — is
the FLOP spot's indifference structure, not the river. Different boards
have different action menus and different indifference manifolds.
Confirming Nash uniqueness on the river does NOT close the question of
Nash multiplicity on the flop. The decision rule in setup doc §6
"Interpretation framework" treats the river run as sufficient to close
A83, which is too strong a claim. We do not have river data to evaluate
that rule either (no strategy was solved).

---

## 5. Implications for the A83 33pp Brown divergence conclusion

The A83 33pp Brown-divergence cells (`3sAs / 3cAc` at `b1000r3000`) were
originally measured via `tests/test_range_vs_range_rust_diff.py` against
the `dry_A83_rainbow` fixture (`docs/a83_deep_cap_root_cause_investigation.md`
§1a-§1c). That test exercises `_rust.solve_range_vs_range_rust` (the
vector-form `dcfr_vector.rs` path), NOT `_rust.solve_hunl_postflop` (the
scalar `hunl_solver.rs` path the Track A nohup used).

The two paths share the noise plumbing (`with_init_noise` is on both)
but differ in:

- **Tree topology:** vector form populates ALL decision infosets up
  front; scalar form lazily inserts on first visit. Both paths apply
  noise correctly in their respective spots (verified by reading
  `dcfr_vector.rs:207-241` and `hunl_solver.rs:353-378`).
- **Hand handling:** vector form runs over a 1081-hand vector at each
  river infoset; scalar form runs one fixed-combo at a time.

Importantly: if the Track A goal is to probe Nash multiplicity on the
EXACT spot where the 33pp divergence was measured, it should use the
SAME entrypoint that produced the original divergence numbers (vector-
form RvR, `_rust.solve_range_vs_range_rust`), not the scalar fixed-combo
postflop path. The scalar path with `hole_cards = None` is a no-op, as
demonstrated above.

So in addition to the no-op bug, there's a path mismatch with the
underlying investigation. The retest needs to call the vector-form
entrypoint directly (Python: `solve_range_vs_range_nash` per
`poker_solver/__init__.py:99`) or via a test/script wrapper, NOT via the
`poker-solver solve` CLI subcommand on its current `hunl-mode postflop`
path.

---

## 6. Recommendation: **REPAIR + RETEST**

### REPAIR (CLI surface)

Two options, in order of effort:

1. **Tightest, lowest-risk:** Add a validate-config check that rejects
   `--hunl-mode postflop` with `initial_hole_cards = None` AND
   `starting_street = River` at the CLI level, before the no-op silently
   completes. This is one-line: change
   `crates/cfr_core/src/hunl_solver.rs::validate_config` to fail-fast
   when `config.initial_hole_cards.is_none() && config.starting_street ==
   Street::River` — or, more conservatively, when `chance_outcomes` would
   be empty at the root. The error should suggest using the
   `solve_range_vs_range_nash` Python entry / a dedicated `poker-solver
   range-vs-range` subcommand for true RvR.

2. **Wider, more correct:** Add a `poker-solver solve --hunl-mode rvr`
   sub-mode that routes to `_rust.solve_range_vs_range_rust` instead of
   `_rust.solve_hunl_postflop`. This is a real product gap — there's
   currently no CLI surface for the vector-form RvR path; users have to
   write Python or use the diff-test harness.

### RETEST (next morning)

Run Track A using the correct entrypoint. Two ways:

- **Quickest:** Write a small Python script that calls
  `poker_solver.solve_range_vs_range_nash` (or imports
  `_rust.solve_range_vs_range_rust` directly) on the
  `dry_A83_rainbow` fixture with the two noise settings, dumps
  per-cell strategy JSONs, and runs the comparison. Iterations
  should match the original investigation's count (per
  `docs/a83_deep_cap_root_cause_investigation.md` §1a — let me
  verify before committing). Outputs go to a JSON file, NOT stdout,
  so the comparison is structured.
- **More correct:** Run on the actual A83 FLOP spot (`As 8s 3s`,
  3-card flop) per the user's underlying interest. This will be a
  longer wall-clock (deeper tree). The setup doc §5 deferred this
  because of wall-clock concerns; if wall-clock is the blocker,
  reduce iter count to whatever produces stable per-cell strategy
  (e.g., 50K iters) rather than skip the spot entirely.

The decision rule from setup doc §6 (`delta >= 0.05` → confirm; `delta <
0.01` → refute; in-between → inconclusive) is still appropriate — but
needs real data to apply.

### What NOT to do

- Do NOT relaunch the same `~/Desktop/a83_track_a_run.sh` script. It
  will reproduce the no-op.
- Do NOT close A83 as "Nash uniqueness confirmed" based on the current
  results. There is no signal in the data either way; the experiment
  did not run.

---

## 7. Side issue worth flagging: Gate 4 turn-phase nohup

`ps aux` shows `pid=42803` running with the same CLI shape:
```
python -m poker_solver.cli solve --game hunl --hunl-mode postflop
  --backend rust --board "As 7c 2d Kh" --stacks 100
  --bet-sizes 33,75,100,150,200 --iterations 200000 ...
```

No `--initial-hole-cards`. By the same mechanism described in §2c, this
SHOULD be a no-op — yet it's been running ~52 minutes of real CPU time.
That's inconsistent with my "no-op" theory if my theory generalizes.

Two possibilities:
1. Gate 4 is ALSO a no-op and the 52 minutes are pure event-loop
   overhead at 200K iters × something (unlikely — `cargo` overhead is
   << 1ms/iter).
2. There's a code path I missed that DOES make the scalar postflop
   path work with `hole_cards = None`. If so, Track A should also have
   been substantive, and the bit-identical output points back to a real
   "noise didn't fire" bug or a real "Nash is unique" finding.

**Action:** before relaunching Track A, run a single quick (~30s)
`poker-solver solve --hunl-mode postflop --backend rust --board "..." --iterations 100`
on a 3-card flop board (forcing deepest tree, hole_cards=None) and
inspect the output to confirm whether the scalar path is broken
universally or only on river. If it's broken universally, Gate 4 is
also invalid and needs its own follow-up.

Do NOT kill Gate 4 to investigate (per task constraints + memory
`feedback_stall_check.md`). Let it complete; check its output afterward.

---

## 8. Summary verdict

| Question | Verdict | Evidence |
|---|---|---|
| Does `--regret-init-noise` flag work? | YES | 3 PR-53 unit tests in `dcfr_vector.rs::tests` PASS |
| Did the 200K-iter Track A nohups solve anything? | NO | 186-byte identical logs, ~111s wall-clock, empty `average_strategy` |
| Per-cell strategy comparison data? | NONE | No rows in either log; no JSON dumps written |
| Wrong-board mismatch (river vs flop)? | DOCUMENTED in setup doc §5; deliberate scope decision (not an agent error); but the underlying interest is the FLOP spot |
| Should we close A83 as "Nash unique"? | NO | Track A did not run; current data is uninformative |
| Recommendation | REPAIR + RETEST | Fix CLI validation; relaunch via the vector-form entry on the actual A83 spot |

### Implications for the A83 33pp gap conclusion

The 33pp Brown-vs-ours gap on bottom-pair-Ace cells at `b1000r3000`
(documented in `docs/a83_deep_cap_root_cause_investigation.md` §1a) is
**still unexplained empirically**. The structural analysis identified two
candidate causes (tree-shape mismatch + terminal-utility convention),
both reasonable. The terminal-utility one has since been arbitrated as
NOT a bug (see superseding banner on the root-cause doc; ref
`docs/terminal_utility_arbitration_2026-05-26.md`). The Nash-multiplicity
hypothesis remains untested.

A correct Track A retest on the A83 spot — using the vector-form RvR
entrypoint — is still the right next step. If retest shows Nash
multiplicity, A83 closes as Type-B (semantic, acceptable Nash
multiplicity at deep-cap indifference). If retest shows Nash uniqueness,
the 33pp gap implicates an unidentified third root cause beyond the two
ruled out by the structural analysis + arbitration.

---

## 9. References

- Launch script: `~/Desktop/a83_track_a_run.sh`
- Setup doc: `docs/a83_track_a_setup_2026-05-26.md`
- PR 53 (flag plumbing): commit `29d608eda8c39228c212c2cb3aba47534a4e5dbc`
- Flag implementation:
  - `crates/cfr_core/src/dcfr_vector.rs:207-241` (vector form constructor)
  - `crates/cfr_core/src/hunl_solver.rs:353-378` (scalar form lazy insert)
- Unit tests:
  - `crates/cfr_core/src/dcfr_vector.rs:1162-1184` (zero reproducibility)
  - `crates/cfr_core/src/dcfr_vector.rs:1199-1255` (epsilon perturbs)
  - `crates/cfr_core/src/dcfr_vector.rs:1262-1291` (seed changes outcome)
- No-op mechanism:
  - `crates/cfr_core/src/hunl.rs:533-568` (`chance_outcomes` returns empty on `hole_cards=None`)
  - `crates/cfr_core/src/hunl_solver.rs:265-282` (scalar chance branch iterates over empty list)
  - `crates/cfr_core/src/exploit.rs:472-475` (uniform fallback on missing strategy keys)
- Underlying A83 investigation: `docs/a83_deep_cap_root_cause_investigation.md`
- Memory rule guiding the retest framing: `feedback_nash_multiplicity_acceptance.md`
