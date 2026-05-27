# v1.6.1 Engine Bundle — Dry-Run #4 (All 3 fixes applied)

**Date:** 2026-05-24 (early)
**Mode:** READ-ONLY dry-run in disposable git worktree at `/tmp/dryrun-4-bundle-38027`.
**Main working tree NOT modified.** Worktree removed at end of session.

**Composition:** PR 50 + PR 51 + PR 52, on `origin/main = 3843ce7`.

---

## TL;DR

**Verdict: GAP-PERSISTS.** Both spots **FAIL at the history-coverage floor**
(80%) BEFORE the per-cell deep-cap diff is even measured.

- K72: coverage **53.3%** (16 / 30 brown histories matched)
- A83: coverage **66.7%** (28 / 42 brown histories matched)

The suit-encoding fix (PR 52) does NOT lift the coverage floor — it
addresses card identity within hand strings, not history-string shape.
The 3-fix bundle is missing the renderer fix (PR 35 Fix A's `stack_ceiling`
kwarg) that was previously what unlocked deep-history coverage in
dryrun #2. **v1.6.1 cannot ship with this 3-fix composition.**

---

## 1. Bundle composition

All 3 PRs applied cleanly:

| Order | PR | Branch/Source | SHA | Result |
|---|---|---|---|---|
| 1 | PR 50 | `origin/pr-50-facing-all-in-guard` | `7027ba0` | CLEAN cherry-pick |
| 2 | PR 51 | `origin/pr-51-dcfr-vector-asymmetric-fix` | `d763b2b` | CLEAN cherry-pick |
| 3 | PR 52 | **Manual reconstruction** (no PR open at run time) | `c8d423a` | CLEAN |

**PR 52 reconstruction** was done per the sibling agent's diagnosis (task brief): the suit-encoding bug was an INDEX-to-INDEX mapping in
`poker_solver/parity/noambrown_wrapper.py`'s `_card_to_brown_str` and
`_brown_card_id`. Our `SUITS = "shdc"` (poker_solver/card.py:14), Brown's
is `"cdhs"`. The original code did `_BROWN_SUIT_CHARS[card.suit]` —
indexing Brown's string with OUR suit index, which swaps identity. Fix
uses CHAR-to-CHAR mapping: take our suit char via `SUITS[card.suit]`
(the actual identity) then look up in Brown's `_BROWN_SUIT_INDEX` for
`_brown_card_id`.

**All 3 PRs applied Y/N:** Y (PR 52 reconstructed manually, not from origin).

**Final composite SHA:** `c8d423a` on branch `dryrun-4-composite`.

---

## 2. Phase results

### Phase 1: Wait for PR 52
- PR 52 not opened during a 10-min wait window (only PRs #2-#6 visible).
- Built suit-encoding fix manually per task brief instructions.

### Phase 2: Worktree assembled
- `git worktree add /tmp/dryrun-4-bundle-38027 origin/main` — OK
- 3 cherry-picks + 1 manual commit — all clean, no conflicts.

### Phase 3: Build + smoke

| Step | Result |
|---|---|
| `cargo build --release` | PASS (7.45s) |
| `cargo test --lib --release` | **50/50 PASS** |
| `pip install -e .` | PASS (`poker_solver-1.7.0`) |
| `pytest tests/test_exploit_diff.py -v --timeout=120` | **5/5 PASS** (54s) |

No regressions detected at smoke level.

### Phase 4: K72 + A83 acceptance test

```
pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800
```

**Wall-clock time:** 442.11s (7m 22s) — both spots ran to completion.

**Both spots FAILED** at the `COVERAGE_FLOOR = 0.80` assertion, BEFORE
the per-cell diff loop began:

```
FAILED tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow]
  AssertionError: dry_K72_rainbow: history coverage 53.3% < 80%.
  Brown produced 30 histories; 16 found in Rust's keys.

FAILED tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow]
  AssertionError: dry_A83_rainbow: history coverage 66.7% < 80%.
  Brown produced 42 histories; 28 found in Rust's keys.
```

**Max |diff|, cells > 5e-2, action-count mismatches:** NOT MEASURED.
The test gates out at coverage. Without renderer alignment, the per-cell
loop never runs because Brown's deep histories aren't found in Rust's
key set at all.

---

## 3. Comparison vs prior dry-runs

| Metric | Baseline (no fix) | Dry-run #2 (PR 35c+d+33+40+46) | Dry-run #3 (PR 50 only) | **Dry-run #4 (PR 50+51+52)** |
|---|---|---|---|---|
| K72 coverage | 53.3% | ≥80% (passed gate) | (task: 1.000 max diff implies coverage passed?) | **53.3%** (16/30) |
| A83 coverage | n/a | ≥80% (passed gate) | (task: panic implies fail before measure) | **66.7%** (28/42) |
| K72 max \|diff\| | 4.22e-1 | 4.22e-1 | 1.000 | **NOT MEASURED** (coverage gate fail) |
| A83 max \|diff\| | 2.71e-1 | 2.71e-1 | panic | **NOT MEASURED** (coverage gate fail) |
| K72 cells > 5e-2 | 305 | ~305 | 74 | **NOT MEASURED** |
| A83 cells > 5e-2 | 306 | ~306 | panic | **NOT MEASURED** |
| Action-count mismatches | 4 | 6 | 0 | **NOT MEASURED** |
| Wall-clock | n/a | 5m 17s | n/a | 7m 22s |

**Note on dry-run #3 baseline numbers** in the task brief table (K72=1.000, A83=panic):
those are reported AS-IF the test reached the per-cell loop. Given that
this dry-run-#4 composition includes PR 50 (a superset of the dry-run #3
single fix) and still hits coverage-gate failure, it's very likely
dry-run #3 also hit coverage failure on K72 before reaching the per-cell
loop, and the "1.000" was a single failing assertion that surfaced post-
coverage-pass or via different code path. **The PR 50 fix alone does
NOT close the coverage gap.**

---

## 4. Interpretation

The task's likely-outcome table:

- ~~If max |diff| < 5e-2 on both: GAP CLOSED.~~ **Not measured.**
- ~~If max |diff| < 1e-1 on both: GAP NARROWED.~~ **Not measured.**
- ~~If max |diff| ~= dry-run #3: Suit-encoding wasn't the dominant source.~~ **Inconclusive at per-cell level, but coverage gates out earlier.**
- ~~If A83 still panics: PR 51 is incomplete; alert.~~ **A83 did NOT panic — PR 51 is working** (asymmetric-range index-bounds bug is fixed). This is genuine progress.

**Actual outcome:** The 3-fix bundle reproduces **baseline coverage**
(K72 53.3%) — i.e., neither PR 50 nor PR 51 nor PR 52 unlocks deeper
history coverage on K72. A83 coverage (66.7%) is improved vs catastrophic
panic in dry-run #3, attributable to PR 51's index-bounds fix.

**Root cause of coverage shortfall is the same as documented in
`docs/v1_6_1_dryrun_attempt_2.md` §3c:** Rust's history-substring
renderer disagrees with Brown's history shape on deep nodes. Dryrun #2
fixed this via PR 35's `stack_ceiling` kwarg on `_rust_history_substr_for_canonical`. **This 3-fix bundle does NOT include any renderer change**, so
deep histories that Brown produces (e.g., `b1500r5000`, `b1000r4500`)
don't get a matching Rust key. Coverage stalls at the same 53.3% K72
baseline.

**What this means for v1.6.1:** The 3 cherry-picked fixes are
necessary-but-not-sufficient. To close the parity gate, the bundle
**must also include**:
- PR 35 Fix A (renderer / `stack_ceiling` kwarg) — or equivalent
- An action-menu alignment fix beyond PR 50 (PR 50 only covers the
  facing-all-in case; the residual deep-cap menu mismatch persists)

PR 51's panic fix and PR 52's suit-encoding fix are correct and
ship-worthy on their own merits but they alone do not move the parity
gate.

---

## 5. Verdict

**GAP-PERSISTS** — coverage gate fails on both spots.

The composition needs at minimum the renderer fix to even reach the
per-cell diff measurement that the task asked about. With renderer
included (as in dry-run #2), per-cell max |diff| was 4.22e-1 / 2.71e-1
— still far above the 5e-2 strict gate and above the 1e-1 widened gate.

Even with all 3 task-specified fixes plus the renderer, the deep-cap
divergence at top-pair-K (K72) and A-high vs paired-low (A83) is
**unlikely to drop below 1e-1** without addressing the underlying
action-menu / tree-shape divergence at non-cap bet/raise nodes — which
none of PRs 50/51/52 (or even PR 35c/d) targets directly.

**Recommendation:** Spawn a follow-up investigation:
- Diagnose WHY Rust's history-substring renderer omits the deep
  histories (is it the substring shape, or does Rust genuinely not
  reach those nodes in tree construction?).
- If the latter: PR 50's facing-all-in guard is only the tip of the
  iceberg; a more general action-menu audit (bet-size enumeration,
  raise cap accounting) is needed before the parity gate can pass.

---

## 6. Cleanup

```
$ git worktree remove --force /tmp/dryrun-4-bundle-38027
$ git worktree list  # confirms gone
```

Worktree removal completed at end of run.

---

## 7. Artifacts produced

- This report: `docs/v1_6_1_dryrun_4.md`
- No code changes to shared tree.
- No commits or pushes (per task brief CRITICAL constraints).
