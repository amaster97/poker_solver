# v1.5.0 Brown Apples-to-Apples Acceptance Test — Empirical Result

**Date:** 2026-05-23
**Task:** Build Brown's `river_solver_optimized` binary and re-run the v1.5.0
acceptance test (`tests/test_v1_5_brown_apples_to_apples.py`) to convert
SKIP → PASS/FAIL.
**Verdict:** **FAIL** — both parametrized spots fail. The Brown
apples-to-apples claim is **not** empirically verified by the current
PR 23 vector-form CFR implementation.

---

## 1. Build outcome

| Field | Value |
| --- | --- |
| Binary path | `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` |
| Size | 206,136 bytes (~201 KiB) |
| Architecture | Mach-O 64-bit executable arm64 |
| Build status | Already built (`scripts/build_noambrown.sh` idempotent path: "Brown's binary already up-to-date") |
| Source mtime | `cpp/src/` last touched 2026-05-20; binary built 2026-05-22 03:32 — newer than every source file, so script confirmed up-to-date |
| `--help` smoke test | Exit 0; prints expected usage banner |

No new compilation was required. The binary from a prior build still passes the
script's idempotency probe and runs cleanly. `cmake` is not currently on `PATH`
on this host, but `scripts/build_noambrown.sh` soft-fails on missing tools and
correctly reused the existing artifact.

---

## 2. Acceptance test verdict — **FAIL (both spots)**

Run command:

```
perl -e 'alarm 600; exec @ARGV' -- pytest tests/test_v1_5_brown_apples_to_apples.py \
    -v -m parity_noambrown -o "addopts="
```

Wall-clock: 316.64 s (~5 min 17 s). Tests completed (no timeout).

| Spot | Verdict | Failure mode |
| --- | --- | --- |
| `dry_K72_rainbow` | **FAIL** | History-coverage floor breached (53.3% < 80%) |
| `dry_A83_rainbow` | **FAIL** | Rust panic in `dcfr_vector.rs:651` (`index out of bounds: the len is 49 but the index is 49`) |

Locked thresholds in the test:

- `COVERAGE_FLOOR = 0.80` (≥80% of Brown's canonical histories must appear in Rust's emitted keys)
- `PER_ACTION_TOL = 5e-3` (per-(hand, action) probability diff)
- `ITERATIONS = 2000`, `DCFR_ALPHA = 1.5`, `DCFR_BETA = 0.0`, `DCFR_GAMMA = 2.0`

---

## 3. Per-spot detail

### 3a. `dry_K72_rainbow` — coverage failure (Python-level assert)

```
AssertionError: dry_K72_rainbow: history coverage 53.3% < 80%.
Brown produced 30 histories; 16 found in Rust's keys.
Either the engines explore different trees (acceptance failure)
or the history canonicalization is mis-rendered (test bug — fix the renderer).
```

- Brown histories: **30**
- Matched in Rust: **16**
- Coverage: **53.3%** (gap to floor: 26.7 pp)
- Per-action TV diff: **not reached** — coverage check is first guard
- Exploitability deltas: **not reported** — test never measured them on a failing coverage path

The two diagnostic branches from the assertion message are:
1. Engines explore different trees (genuine algorithmic gap — PR 23 vector CFR's
   action enumeration / history rendering diverges from Brown's `RiverGame` tree
   in ~half the canonical states).
2. The Brown→Rust history canonicalization renderer mis-renders ~half of
   Brown's keys (test bug — the substring shape it builds does not match Rust's
   emitted `<hole_string>|<key_suffix>` format).

Either way, the test is not currently a passing acceptance gate.

### 3b. `dry_A83_rainbow` — Rust panic (engine-level abort)

```
thread '<unnamed>' (29025946) panicked at crates/cfr_core/src/dcfr_vector.rs:651:22:
index out of bounds: the len is 49 but the index is 49
```

`crates/cfr_core/src/dcfr_vector.rs:651` is the line
`total += reach_opp[ho] * utility;` inside the terminal-utility expectation
loop. The opponent-reach vector has length 49 but the loop iterates a hole
index that reaches 49 (i.e., off-by-one or stale-length bug — the loop bound
and the slice length disagree by one).

This is an outright crash, not a tolerance miss — the Rust vector-form CFR
does not finish a single `solve_range_vs_range_rust` call on this spot. No
strategy is emitted, so no per-action diff or coverage measurement is
possible.

---

## 4. Interpretation

Both failures are **engine-side**, not tolerance-side:

- `dry_K72_rainbow` failed the *first* gate (coverage), well before any
  numerical tolerance comparison. Tightening or loosening `PER_ACTION_TOL`
  would not help; the test never reached that assertion.
- `dry_A83_rainbow` panicked inside `_rust.solve_range_vs_range_rust` itself.
  This is a Rust-side bug (index/length mismatch in the terminal-utility
  expectation), not a Nash-mixed-strategy non-uniqueness issue.

The v1.5.0 "true Nash range-vs-range" headline — that PR 23's Rust vector-form
CFR matches Brown's `river_solver_optimized` on the same hand set within
documented tolerances — is **not currently supported by empirical evidence**.

This contradicts the task framing's hopeful read of the burst's load-bearing
fix. The build was never the bottleneck (binary was already valid). The
bottleneck is the PR 23 implementation itself.

---

## 5. Recommended next step

**Do not ship task #182 ("flip SKIP → PASS in release notes") until the
underlying Rust engine bugs are fixed.** Tightening the tolerance is not
applicable; the gates that failed are pre-tolerance (coverage floor and a
hard panic).

Concrete prioritized actions:

1. **Triage the `dcfr_vector.rs:651` index-out-of-bounds panic (P0).**
   - Reproduce with `RUST_BACKTRACE=1 pytest tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow] -v -m parity_noambrown -o "addopts="`
   - Audit the loop bound vs `reach_opp.len()` at the call site; check whether
     `ho` is iterating Brown's hand-list (50) while `reach_opp` was built for
     49 (or vice versa) — the off-by-one signature is sharp.
   - Add a debug assertion guarding the bound so future regressions surface
     deterministically rather than crashing PyO3.

2. **Diagnose the `dry_K72_rainbow` 53.3% coverage failure (P0).**
   - Dump both Brown's canonicalized history strings and Rust's emitted keys
     side-by-side for this spot. Identify which 14/30 histories Brown sees
     that Rust never produces (or produces under a different rendering).
   - Decide which side is wrong: if Rust's tree is genuinely smaller, the
     vector-form CFR is missing branches (algorithmic gap, requires a PR 23
     follow-up); if the substring renderer in the test mis-encodes Brown's
     `b<amount>` shape, fix the renderer (test bug). The assertion message
     enumerates both branches deliberately.

3. **Hold task #182 (release-notes verdict flip) until both gates pass.**
   The PLAN.md item should remain "SKIP-pending-fix", not "PASS-pending-binary".
   The acceptance test, as written, is now diagnostic — it will report the
   correct verdict once the engine is fixed.

4. **Do NOT tighten or loosen tolerances yet.** PER_ACTION_TOL = 5e-3 and
   COVERAGE_FLOOR = 0.80 are derived from PR 7 §1 + PR 23 spec §5 Case B and
   are the appropriate gates. The failures observed here are not tolerance
   problems.

5. **Consider opening a follow-up PR** scoped to:
   - Fix `dcfr_vector.rs` index bug
   - Audit / fix the Brown→Rust history-canonicalization renderer (or the
     Rust tree it compares against)
   - Re-run this exact acceptance test as the merge gate

---

## 6. Reproduction recipe (for the follow-up agent)

```bash
# 1. Confirm Brown binary is present (idempotent):
bash /Users/ashen/Desktop/poker_solver/scripts/build_noambrown.sh

# 2. Confirm Rust .so is fresh (already May 23 06:49 in shared tree):
python -c "import poker_solver._rust as r; print(hasattr(r, 'solve_range_vs_range_rust'))"

# 3. Re-run the acceptance test (5e-3 tolerance, 80% coverage floor):
perl -e 'alarm 600; exec @ARGV' -- \
    pytest tests/test_v1_5_brown_apples_to_apples.py \
        -v -m parity_noambrown -o "addopts="

# 4. For the dry_A83_rainbow panic, enable backtrace:
RUST_BACKTRACE=1 perl -e 'alarm 600; exec @ARGV' -- \
    pytest 'tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow]' \
        -v -m parity_noambrown -o "addopts="
```

---

## 7. Source-of-truth pointers

- Acceptance test: `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
- Brown source: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/`
- Brown binary: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
- Panic site: `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs:651`
- Apples-to-apples doc: `/Users/ashen/Desktop/poker_solver/docs/brown_apples_to_apples_2026-05-23.md`
- Build script: `/Users/ashen/Desktop/poker_solver/scripts/build_noambrown.sh`
- Run log (transient): `/tmp/v1_5_brown_acceptance_run.log`
