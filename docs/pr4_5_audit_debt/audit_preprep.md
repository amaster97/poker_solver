# PR 4.5 audit pre-prep — anticipated findings + sequencing

**Status:** PRE-STAGED. Audit cycle has not yet run. PR 4.5 itself has not
yet fired (gated behind PR 5 + PR 6 landing). This doc enumerates what the
audit agent is likely to flag, what verdict to expect, and how to sequence
the audit relative to the rest of the PR pipeline.

**Read-only / prep doc.** No source edits; no test edits.

**Authoritative scope:** `launch_kickoff.md` §2 (13 items locked).
**Authoritative fan-out:** `fanout_ready.md` §3 (3-agent ownership matrix).
**Audit target file (will be written by audit agent):**
`docs/pr4_5_audit_debt/audit_report.md`.

---

## 1. Likely audit findings (per the 8 anticipated categories)

### 1.1 Mechanical-only scope creep (must-fix gate)

PR 4.5 is the "no behavior change" PR. Audit verifies NO addition beyond
the documented 13 items. High-probability scope-creep vectors:

- Agent A discovering an adjacent `AssertionError` outside the rake-fields
  scope (3-C is specifically `__post_init__` rake-field validators, not the
  whole module). Audit flags any `AssertionError → ValueError` swap not
  explicitly cited in §2.
- Agent B over-tightening the SHOWDOWN predicate (4-B) by also touching the
  `_is_terminal` guard in `hunl_solver.py`. 4-B is one line at `hunl.py:336`,
  not a solver refactor.
- Agent B "improving" the `max_boards_per_street` autosize (4-D) by changing
  the autosize threshold from 5000. The kwarg is a surface change; the
  internal threshold stays.
- Any new test addition (kickoff §3: "test coverage additions" deferred).

**Audit verdict trigger:** must-fix if scope creep changes observable
behavior; should-fix if creep is benign (docstring expansion, type
annotation). Revert benign creep too — keeps PR 4.5's purpose pure.

### 1.2 PR 3 mechanical fixes (low-risk; expected clean)

3-A / 3-B license headers: text drift across `hunl.py`, `action_abstraction.py`
is the only realistic finding. Aggregator normalizes wording (kickoff §8d).
3-C `ValueError` swap: audit confirms the corresponding test
(`pytest.raises(AssertionError)` → `pytest.raises(ValueError)`) updated in
the same PR; otherwise must-fix.
3-D `field` import drop: pre-grep that `field(` isn't referenced elsewhere
in `hunl.py` (kickoff §8e). Audit re-greps.
3-E unreachable assert: audit confirms the `assert False` doesn't fire in CI;
kickoff §8c says revert + file follow-up if it does.

**Expected:** all 5 items clean per audit.

### 1.3 PR 3.5 must-fixes already landed (do NOT re-do)

Confirm in commit `1cbf52a` (per kickoff §3 defer list). Audit cross-checks
that PR 4.5 does NOT re-implement public-API rename, `ValueError`, backend
string, or chart-metadata scalars. If any of those surface in the PR 4.5
diff, must-fix revert (duplicate / drift risk).

The three PR 3.5 items IN scope are 3.5-A (`PushFoldChartUnavailable(ValueError)`),
3.5-B (drop `v1-placeholder`), 3.5-C (remove dead `_canonical_hand_classes`).
3.5-A requires `except PushFoldChartUnavailable` consumer grep first
(kickoff §9b must-fix trigger).

### 1.4 PR 4 polish items

- **4-A license header on `equity_features.py`:** parallels 3-A / 3-B; check
  text consistency.
- **4-B SHOWDOWN predicate tighten:** audit confirms test
  `test_infoset_key_*` updated per kickoff §8b. SHOWDOWN is terminal per
  spec — `infoset_key` at SHOWDOWN should never be called by solver. If it
  was, the predicate was masking a latent bug; surface it.
- **4-C `_kmeans_plusplus_init` unreachable assert:** same pattern as 3-E.
  If `assert False` trips in CI, the empty-cluster fallback was reachable —
  k-means quality regression. Revert + follow-up (kickoff §8c).
- **4-D `mc_iterations` autosize kwarg:** surface-only. Audit confirms no
  internal threshold change; default behavior preserved for callers passing
  no kwarg.

### 1.5 PR 5 cleanup

5-A: drop unused `numpy` import + `_ = np` suppression in `profiler/memory.py`.
Audit re-greps `np\.` in `profiler/memory.py`; if any `np.ndarray` type
annotation or other reference exists, the import drop fails mypy (kickoff §8e).

**Most defer-listed PR 5 items fold into PR 4.5 only if scope expands.** Per
kickoff §3, 6 skip-marked TURN tests + 5-M1 lossless-flop hang stay deferred.
Audit verifies neither leaks into PR 4.5 diff.

### 1.6 Test regression

PR 4.5 must NOT introduce new test failures. Pre-PR-4.5 baseline test count
captured per `fanout_ready.md` §1 (optional pytest sanity run). Post-PR-4.5
must equal baseline modulo:
- 3-C: rake-config test exception-type swap (`AssertionError` →
  `ValueError`). Same test, same count.
- No new tests added (kickoff §3 defer).
- No tests skip-marked or deleted.

Audit cross-checks test count + skip count.

### 1.7 Cross-agent file ownership (concurrent-edit collision check)

Per `fanout_ready.md` §3 ownership lock:
- Agent A owns `hunl.py` lines 14, 107, 109 + license header.
- Agent B owns `hunl.py:336` only.
- Line ranges do NOT overlap; git auto-merges.

Audit verifies the merge was clean (no manual conflict resolution that could
have introduced drift). Check git log for any merge-conflict resolution
commits on the PR 4.5 branch.

### 1.8 Total LOC delta

Mechanical fixes should net **<50 LoC total** per `launch_kickoff.md` §12
("Total: 7 source files; ~30–50 LoC delta expected, mostly subtractions +
one-line additions"). Audit flags if delta exceeds 50 net LoC — signal of
scope expansion beyond mechanical fixes.

Subtraction-heavy: `field` import drop, dead `_canonical_hand_classes`,
`numpy` import drop, `v1-placeholder` entry, plus 3 one-line license
headers + a handful of one-line predicate / exception-class tightenings.

---

## 2. Expected verdict: READY

PR 4.5 is a curated mechanical sweep — all 13 items pre-audited at source
(per PR 3 / 3.5 / 4 / 5 audit reports). Audit should be clean: zero must-fix,
0–2 should-fix (most likely license-header text drift per kickoff §8d, easily
normalized by aggregator).

**Conditions that flip verdict to NOT READY:**
- Scope creep (§1.1) introduces behavior change.
- Unreachable assert (3-E or 4-C) trips in CI → latent bug surfaced.
- Test regression (§1.6) outside the 3-C exception-type swap.
- LOC delta exceeds 50 net (§1.8).
- `PushFoldChartUnavailable(ValueError)` change (3.5-A) breaks an `except`
  consumer that wasn't pre-grepped (kickoff §9b).

Expected actual outcome: **READY**, with a short should-fix list (license
text consistency, possibly one mypy nit on the `numpy` drop).

---

## 3. Sequencing recommendation

**Default: fire PR 4.5 AFTER PR 6 lands** (and after its own audit cycle).

Rationale (extends `launch_kickoff.md` §4):
1. PR 6 is the Rust port. If PR 6 rewires `_kmeans_plusplus_init` (4-C) or
   `precompute.py` autosize (4-D), PR 4.5's Python cleanup becomes no-op or
   harmful (Python/Rust drift).
2. PR 6 has its own audit cycle. Firing PR 4.5 before PR 6's audit lands
   risks rabbit-holing PR 4.5's own audit on items that PR 6 may have
   already fixed (4-C / 4-D especially).
3. K-means quality assessment needs production-scale evidence (PR 6 unlocks
   full enumeration). Per "Don't extrapolate" memory rule.
4. Audit-debt clearance compounds when batched (kickoff §4 point 4).

**Alternative: fire AFTER PR 5 only**, narrowed scope (drop 4-C / 4-D / 5-A
to defer until post-PR-6). Cost: ~1 hr duplicate review when PR 6 lands and
4-C / 4-D need re-touch. Benefit: faster audit-debt-zero for PR 3 / 3.5 / 4
polish items.

**NOT recommended:** fire before PR 5 merges. `hunl_solver.py` + surrounding
files are in flux until PR 5 lands.

---

## 4. PR 4.5 alternative scope (if 13 items too aggressive)

Subset option: **just PR 3.5 + PR 4 polish** (8 items).

- Drop: 3-A, 3-B, 3-C, 3-D, 3-E (PR 3 items — 5 items).
- Drop: 5-A (PR 5 item — 1 item).
- Keep: 3.5-A, 3.5-B, 3.5-C (3 items).
- Keep: 4-A, 4-B, 4-C, 4-D (4 items).

Total: 7 items. Cost: defer PR 3 license headers + `field` import drop +
exception-type swap to a future cleanup PR. Trade-off: cleaner audit on the
"more interesting" mechanical fixes (predicate tightening, unreachable
asserts, kwarg surface) without bundling license + import housekeeping.

**Recommended only if:**
- PR 3-era files (`hunl.py`, `action_abstraction.py`) are in active edit by
  another PR at PR 4.5 launch time (collision risk).
- User signals "small audit-debt PR first; defer trivia."

Default remains 13 items.

---

## 5. Audit agent prompt (cross-reference)

When PR 4.5 fires and audit runs (kickoff §9b):

> "Audit branch `pr-4.5-audit-debt-sweep` against the 13 items in
> `docs/pr4_5_audit_debt/launch_kickoff.md` §2; flag any behavior change or
> scope creep; cross-reference findings against
> `docs/pr4_5_audit_debt/audit_preprep.md` §1 (anticipated findings); write
> report to `docs/pr4_5_audit_debt/audit_report.md`."

The audit_preprep checklist (§1.1–1.8 above) is the audit agent's pre-flight
list. Categorize each finding against this taxonomy in the audit report.

---

## 6. Quick-reference paths

- `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md` — canonical scope + fan-out.
- `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/fanout_ready.md` — operational shortlist.
- `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_report.md` — written post-fan-out (does not yet exist).
- `/Users/ashen/Desktop/poker_solver/docs/cross_pr_cleanup_plan.md` — cross-PR cleanup canonical source.
- `/Users/ashen/Desktop/poker_solver/docs/audit_followup_backlog.md` — full backlog; PR 4.5 is a strict subset.
- Per-PR audits: `docs/pr{3,3_5,4,5}_prep/audit_report.md`.
- Commit `1cbf52a` — PR 3.5 follow-up (must-fixes 1–5 already landed; PR 4.5 does NOT re-do).
