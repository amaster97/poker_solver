# PR 4.5 launch decision — fire now (concurrent with PR 7) or defer?

**Verdict:** **DEFER until PR 7 commits to `integration`.**

**Date:** 2026-05-22.
**Decision input:** `launch_kickoff.md` §4 + §5a; `fanout_ready.md` §1 + §3; `audit_preprep.md` §3.
**Status pre-decision:** PR 6 has merged (integration tip `6c438b8` per orchestrator note). PR 7 is in-flight on `tests/` slice. PR 5 + PR 6 prerequisites for PR 4.5 are SATISFIED (kickoff §4 default sequencing met).

---

## 1. File-scope overlap with PR 7

**Result:** zero overlap.

- **PR 4.5 write set** (kickoff §12 / fanout §3 ownership matrix): 7 files, all under `poker_solver/`:
  - `poker_solver/hunl.py`
  - `poker_solver/action_abstraction.py`
  - `poker_solver/pushfold.py`
  - `poker_solver/abstraction/equity_features.py`
  - `poker_solver/abstraction/emd_clustering.py`
  - `poker_solver/abstraction/precompute.py`
  - `poker_solver/profiler/memory.py`
- **PR 7 write set** (per orchestrator note): `tests/` + `tests/fixtures/` only.

No file is touched by both. Concurrent execution is mechanically safe — git would auto-merge with no conflict.

**Caveat (low risk):** PR 4.5 includes one test edit (kickoff §8a: `pytest.raises(AssertionError)` → `pytest.raises(ValueError)` on rake-config test, in same PR as 3-C). That test file lives in `tests/`. If PR 7 happens to touch the same rake-config test file, the agents would collide. Likelihood: low (PR 7 is a separate test slice), but not zero.

---

## 2. Branch creation from `integration` tip `6c438b8`

**Result:** OK in principle, but pre-flight gate 1a (kickoff §6a / fanout §1a) requires that **PR 5 + PR 6 are both visible on `integration`**. Per orchestrator note, `6c438b8` carries PR 6. The kickoff's default sequencing also requires PR 5 — assume PR 5 is upstream of `6c438b8` (would have to verify with `git log --oneline integration -10` at fire time).

Pre-flight gates 1b–1e (origin sync, clean tree, audit reports present, reflog backup) are standard and orthogonal to the launch-now-vs-defer question. Branch creation itself is risk-free; the gating issue is whether to fire at all.

---

## 3. Serial vs parallel against PR 7

Three factors push toward defer:

1. **Mental-model simplicity.** Per orchestrator-only memory rule, the orchestrator's job is aggregation + scheduling, not concurrent merge-conflict resolution. Even with disjoint file sets, two PR pipelines in flight means two audit cycles to track, two check_pr.sh runs to interpret, two commit/push/merge sequences to sequence on `integration`. Audit-debt cleanup is **not on critical path**; serial flow is cheaper cognitively.
2. **PR 7 audit may surface item that affects PR 4.5 scope.** PR 7 touches `tests/` — if it adds tests that exercise the rake-config path (3-C) or SHOWDOWN predicate (4-B), the test edits PR 4.5 needs (§8a, §8b) shift. Landing PR 7 first locks the test surface before PR 4.5 modifies it.
3. **`min-five-agents` floor is not at risk by deferring.** The user memory rule requires ≥5 concurrent agents in autonomous sessions, but reviewer / prune / log-housekeeping fillers count. PR 4.5's 3-agent fan-out is not the only way to maintain the floor; spawning it during PR 7 doesn't add critical-path throughput.

**Counterargument considered:** parallel-agents-default memory rule says fan out independent tracks. PR 4.5 IS independent from PR 7 mechanically. But "independent" in the memory rule means agent-level parallelism within a single PR pipeline, not whole-PR parallelism that doubles the orchestrator's tracking surface. PR 4.5 is non-critical-path audit-debt cleanup; defer is the conservative serial path.

---

## 4. Top 2 considerations

1. **PR 4.5 is non-critical-path.** It's mechanical audit-debt cleanup, not feature work. Serial-after-PR-7 costs ~90 min wall-clock delay (one PR cycle); concurrent saves ~90 min but doubles orchestrator audit-tracking surface during that window. The marginal time savings does not justify the complexity cost on a non-blocking PR.
2. **Test-surface lock.** PR 7 modifies `tests/`. PR 4.5's §8a rake-test exception-type swap and §8b SHOWDOWN-test update both touch tests. Even if PR 7 doesn't touch those specific tests, landing PR 7 first means PR 4.5 modifies a stable `tests/` baseline rather than racing against in-flight test changes. Cleaner audit narrative.

---

## 5. Recommended action

- **Now:** do NOT launch PR 4.5. Let PR 7 complete its full pipeline (agent fan-out → audit → commit → merge to `integration`).
- **After PR 7 merges:** re-run pre-flight gate (`fanout_ready.md` §1) against new `integration` tip. If gate passes, fire PR 4.5 per kickoff §5–9.
- **Estimated delay:** ~1 PR cycle (PR 7 wall-clock TBD; bounded by its own audit + commit pipeline).

No changes to PR 4.5 scope or fan-out plan. Defer is purely scheduling.
