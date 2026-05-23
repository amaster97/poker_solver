# PR 4.5 launch kickoff — cross-PR audit-debt sweep

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 5 + PR 6 have merged
to `integration` and the user has approved firing PR 4.5. See §4 for the
sequencing recommendation.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs
when PR 4.5 is next on deck. Bundles 13 mechanical fixes from the PR 3, 3.5,
4, 5 audit reports into a single short cleanup PR. No behavior changes.

**Branch:** `pr-4.5-audit-debt-sweep` (PLAN.md §1 "Per-PR feature branches
from PR 3 onward").

**Wall-clock estimate:** ~90 min total (~60 min parallel agent waves + ~30 min
aggregator). Net throughput vs sequential is ~2.5x.

**Canonical scope source:**
- `/Users/ashen/Desktop/poker_solver/docs/cross_pr_cleanup_plan.md` (§2 + §4)
- `/Users/ashen/Desktop/poker_solver/docs/audit_followup_backlog.md` (full backlog; this PR is a strict subset)
- Per-PR audits: `docs/pr3_prep/audit_report.md`, `docs/pr3_5_prep/audit_report.md`, `docs/pr4_prep/audit_report.md`, `docs/pr5_prep/audit_report.md`

---

## 1. Goal

Bundle 13 mechanical fixes from the PR 3 / 3.5 / 4 / 5 audit reports into one
short cleanup PR. Shared property: **single agent reading the audit line can
fix mechanically in <15 min with no spec interpretation.**

Batched-PR wins vs piecemeal drift: single audit cycle (~3 overheads saved),
one CHANGELOG entry, audit-debt-zero state going into PR 7+ feature work.

Explicitly NOT behavior-change. Every fix preserves observable behavior;
changes are error-type narrowing (`ValueError` subclasses), license header
text, predicate tightening on unreachable branches, dead-code removal,
magic-number sentinels, and import drops.

---

## 2. Scope (explicit fix list — 13 items)

### Source: PR 3 audit (`docs/pr3_prep/audit_report.md`)
- **3-A.** License-posture header line on `poker_solver/hunl.py` (audit L154-158 "License compliance"). One-line: "no third-party code derivation; original implementation."
- **3-B.** Same one-line header on `poker_solver/action_abstraction.py`.
- **3-C.** `AssertionError` → `ValueError` in `HUNLConfig.__post_init__` rake fields (Nice-to-fix #1; hunl.py:107, 109). Same file already uses `ValueError` at lines 112, 114, 119, 126.
- **3-D.** Remove unused `field` import from `hunl.py:14` (Nice-to-fix #8).
- **3-E.** Mark `enumerate_legal_actions` stack≤0 branch unreachable in `action_abstraction.py:210-211` (Should-fix; defensive but currently unreachable per `all_in[p]` invariant).

### Source: PR 3.5 audit (`docs/pr3_5_prep/audit_report.md`)
- **3.5-A.** Make `PushFoldChartUnavailable` subclass `ValueError` in `pushfold.py:30` (Should-fix #2). Downstream `except ValueError` consumers now catch it.
- **3.5-B.** Drop `v1-placeholder` from `PUSHFOLD_CHART_VERSIONS` in `pushfold.py:25` (Should-fix #8). Loader must reject dry-run output.
- **3.5-C.** Remove dead `_canonical_hand_classes()` in `pushfold.py:185` (Nice-to-fix #7; only `_all_hand_classes()` is called by `get_full_range`).

### Source: PR 4 audit (`docs/pr4_prep/audit_report.md`)
- **4-A.** License-posture header on `poker_solver/abstraction/equity_features.py` (Should-fix #1). One-line: "no third-party code derivation; equity feature is original."
- **4-B.** Tighten SHOWDOWN predicate at `hunl.py:336` (Should-fix #2). Change `state.street >= Street.FLOP` to `state.street in (Street.FLOP, Street.TURN, Street.RIVER)`. Currently latent (solver's `is_terminal` guard masks it).
- **4-C.** Mark `_kmeans_plusplus_init` empty-cluster fallback unreachable at `emd_clustering.py:188-196` (Should-fix #5). Replace `chosen_idx[c] = chosen_idx[0]` with `assert False, "unreachable; n < K branch handled at line 167"`.
- **4-D.** Surface `mc_iterations < 5000` autosize trigger as explicit kwarg at `precompute.py:452-455` (Should-fix #7). Add `max_boards_per_street=None` sentinel for "use autosize" + `-1` for "no cap."

### Source: PR 5 audit (`docs/pr5_prep/audit_report.md`)
- **5-A.** Drop unused `numpy` import + `_ = np` suppression at `profiler/memory.py:508-510` (Nice-to-fix N3 + N5).

**Total: 13 items.**

---

## 3. Out of scope (explicit defer list)

- **K-means quality tuning** (PR 4 centroid count, EMD tolerance, mc_iterations defaults). **Defer to post-PR-6** so quality can be assessed at production scale; Rust port enables full enumeration and may invalidate Python-tuning intuitions.
- **`save_abstraction` byte-determinism via timestamp override** (PR 4 Should-fix #4). Needs design decision; no current downstream consumer. Defer to future content-addressable-cache PR.
- **6 skip-marked PR 5 tests** (TURN coverage gap; audit G1-G6). Needs smaller fixture redesign or PR 6 Rust resolution of `lookup_bucket` TURN hang. **Defer to PR 6 acceptance.**
- **5-M1 lossless-flop exploitability hang** (PR 5 must-fix). Lands as part of PR 5 itself per `open_items_audit_2026-05-22.md` recommendation 2.
- **PR 3.5 §6 must-fixes 1-5** (public API rename + ValueError + backend string + chart metadata scalars). Already landed in PR 3.5 follow-up commit `1cbf52a`; audit reports describe pre-followup state.
- **Spec-amendment-requiring items** (PR 3 `HUNLState.config` source-of-truth; PR 3.5 d=2 universal-jam landmark; PR 3.5 strategic-equivalence collapse). Each requires strategic decision; not mechanical.
- **`_canonicalize` / `_apply_suit_perm_to_hand` rename to spec names** (PR 4 Nice-to-fix #1). Touches buckets.py + tests; roll into next PR touching buckets.py.
- **CLI integration items** (PR 3.5 `--hunl-mode pushfold`; PR 5 `--abstraction PATH` flag). Belong in next PR with CLI surface changes.
- **Test coverage additions** (PR 4 coverage gaps 1-6; PR 5 G1-G6; PR 3.5 `test_pushfold_regen.py` smoke). New tests are not mechanical-fix scope.
- **Magic-constant calibration** beyond Item 4-D (e.g., `_DICT_OVERHEAD_RATIO`). Per backlog §4 "safe to defer indefinitely."

If any deferred item is reclassified, add to §2 and update §5 ownership;
do NOT silently extend scope mid-execution.

---

## 4. Sequencing recommendation

**Default: fire AFTER PR 5 + PR 6 have both merged to `integration`.**

Rationale:
1. **PR 5 has its own must-fix queue.** 5-M1 lands as part of PR 5's pre-commit gates. Firing PR 4.5 before PR 5 duplicates audit-debt review on `hunl_solver.py`.
2. **PR 6 (Rust port) may invalidate PR 4 items.** If Rust re-implements `_kmeans_plusplus_init` (4-C) or rewires `precompute.py` autosize (4-D), Python cleanup becomes no-op or actively harmful (drift between Python reference + Rust production).
3. **K-means quality needs production-scale evidence** (per "Don't extrapolate" user-memory rule). PR 6 unlocks full enumeration.
4. **Audit-debt clearance compounds when batched.** Firing after both PRs consolidates audit-debt-zero state immediately before PR 7+.

**Alternative: fire AFTER PR 5 ONLY** (before PR 6). Cost: ~1 hr duplicate
review when PR 6 lands and 4-C / 4-D need re-touch.

**NOT recommended:** fire before PR 5 merges. `pyproject.toml` +
`hunl_solver.py` surface is in flux until PR 5 lands.

---

## 5. Three-agent fan-out plan

### 5a. Ownership matrix

| Agent | Owns (write/edit) | Read-only on |
|---|---|---|
| A | PR 3/3.5: `hunl.py`, `action_abstraction.py`, `pushfold.py` | `docs/pr{3,3_5}_prep/audit_report.md` |
| B | PR 4: `abstraction/equity_features.py`, `abstraction/emd_clustering.py`, `abstraction/precompute.py`, predicate at `hunl.py:336` | `docs/pr4_prep/audit_report.md` |
| C | PR 5: `profiler/memory.py` | `docs/pr5_prep/audit_report.md` |

**Shared-edit caveat for Item 4-B:** `hunl.py:336` is in Agent A's file but
originates from PR 4's audit. Pre-coordinate: Agent A patches lines 14, 107,
109 (Items 3-C, 3-D); Agent B patches line 336 (Item 4-B). The line ranges do
not overlap; git auto-merges trivially.

### 5b. Per-agent scope

**Agent A (PR 3/3.5 mechanical, ~30 min):** Items 3-A, 3-B, 3-C, 3-D, 3-E, 3.5-A, 3.5-B, 3.5-C (8 items).
**Agent B (PR 4 mechanical, ~30 min):** Items 4-A, 4-B, 4-C, 4-D (4 items).
**Agent C (PR 5 mechanical, ~15 min):** Item 5-A (1 item).

**Acceptance per agent:** relevant per-PR test slice passes; `mypy --strict
poker_solver/` clean; `ruff check` clean.

### 5c. Launch sequence (all three in one tool-call block)

Each of 3 agent tool calls: `subagent_type: general-purpose`,
`run_in_background: true`, description per §5b ("PR 4.5 Agent {A|B|C} —
{slice} mechanical audit-debt fixes"). Prompt body must (a) list items from
§2 with audit-report citations, (b) cite ownership row from §5a, (c) state
"mechanical fixes only; no behavior changes; no new tests; no docstring
expansions beyond the one-line items," (d) cite this kickoff doc as canonical
scope source.

**Parallel fan-out during agent runtime** (per parallel-agents-default user
memory): orchestrator may launch independent agents on PR 7 spec polish,
`docs/autonomous_log.md` housekeeping (continuous-pruning rule), or doc
inventory sweep. Aggregate per wave — do NOT react agent-by-agent.

---

## 6. Pre-flight gate

All five checks must pass.

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. PR 5 + PR 6 are both merged to integration (default sequencing).
git fetch origin
git log --oneline integration -10
# Expected: integration tip includes both PR 5 + PR 6 merge commits.

# 6b. integration tip matches origin/integration.
git rev-parse integration
git rev-parse origin/integration
# Hashes must be equal. If not: `git pull --ff-only origin integration`.

# 6c. Working tree clean.
git status
# Expected: "nothing to commit, working tree clean".

# 6d. All audit reports + cleanup plan present.
ls -la docs/cross_pr_cleanup_plan.md docs/audit_followup_backlog.md
ls -la docs/pr3_prep/audit_report.md docs/pr3_5_prep/audit_report.md
ls -la docs/pr4_prep/audit_report.md docs/pr5_prep/audit_report.md

# 6e. Reflog backup.
git rev-parse integration > /tmp/integration_pre_pr_4_5.hash
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green;
test-count becomes the post-PR-4.5 regression bar.

---

## 7. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-4.5-audit-debt-sweep
git status   # expect: clean tree, on pr-4.5-audit-debt-sweep
```

Branch name is fixed and audit-prompt-cross-referenced; do NOT improvise.

---

## 8. Monitor + reconciliation patterns

While agents run, orchestrator does NOT block. PR 4.5-specific signatures:

- **8a. Item 3-C breaks `pytest.raises(AssertionError)`** on rake config path. Update test to `pytest.raises(ValueError)` in SAME PR (part of the mechanical fix, not scope creep).
- **8b. Item 4-B breaks `test_infoset_key_*`.** Test is calling `infoset_key` at SHOWDOWN. Update test (SHOWDOWN is terminal per spec) or revert 4-B. Default: update the test.
- **8c. Unreachable assert (3-E, 4-C) trips in CI.** Branch was reachable — latent bug surfaced. STOP, revert the assertion, file follow-up must-fix. Do NOT downgrade to `pass`.
- **8d. License header text drift across 3-A, 3-B, 4-A.** Aggregator normalizes wording. Should-fix, not must-fix.
- **8e. mypy regression after import drops (3-D, 5-A).** Removed import referenced elsewhere (e.g., `numpy.ndarray` in type annotation). Pre-grep `field(` and `np\.` BEFORE removing; skip if non-trivially used.

---

## 9. Audit + commit pipeline

### 9a. Interface drift reconciliation (after all 3 agents return)

```sh
cd /Users/ashen/Desktop/poker_solver
pytest -x              # full suite green
mypy --strict poker_solver/
ruff check
```

Drift patterns: license header text drift (§8d); 4-B predicate edit conflicts
with 3-C / 3-D on `hunl.py` (no line overlap; git auto-merges).

Test-count must equal pre-PR-4.5 baseline (no test deletions; mechanical
fixes do not change tests except possibly the rake-exception type).

### 9b. Audit + check battery in parallel

```sh
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_4_5_output.log 2>&1
```

Concurrently, launch audit agent (prompt: "Audit branch
pr-4.5-audit-debt-sweep against the 13 items in
`docs/pr4_5_audit_debt/launch_kickoff.md` §2; flag any behavior change or
scope creep; write report to `docs/pr4_5_audit_debt/audit_report.md`").

**PR 4.5-specific must-fix triggers:**
- Any behavior change beyond the 13 items.
- Test deletion or skip-marking introduced by the cleanup.
- License header wording drift across the 3 modules.
- `PushFoldChartUnavailable(ValueError)` change breaks an `except PushFoldChartUnavailable` consumer (grep first).
- Unreachable-assert fires in CI (per §8c).

**Should-fix triggers:** new mypy/ruff warnings; item not implemented per §2 letter.

### 9c. Commit

```sh
git status   # verify staged set
git add poker_solver/ docs/pr4_5_audit_debt/audit_report.md
git commit -m "$(cat <<'EOF'
PR 4.5: cross-PR audit-debt sweep (mechanical fixes only)

Bundles 13 should-fix / nice-to-fix items from the PR 3 / 3.5 / 4 / 5 audit
reports into one cleanup PR. No behavior changes; no spec amendments.

Items (see docs/pr4_5_audit_debt/launch_kickoff.md §2):
- PR 3/3.5: license headers (hunl.py, action_abstraction.py), AssertionError
  to ValueError on rake config, unused import drop, unreachable assert in
  enumerate_legal_actions, PushFoldChartUnavailable(ValueError), drop
  v1-placeholder, remove dead _canonical_hand_classes.
- PR 4: license header (equity_features.py), SHOWDOWN predicate tighten in
  infoset_key, unreachable assert in _kmeans_plusplus_init,
  max_boards_per_street sentinel surface in precompute.
- PR 5: drop unused numpy import in profiler/memory.py.

Out of scope (deferred per launch_kickoff.md §3): kmeans tuning (post-PR 6),
byte-determinism design, 6 skip-marked PR 5 tests (PR 6 resolves), spec
amendments, CLI integration items.

Test result: <X>/<X> pass (baseline pre-PR-4.5: <Y>/<Y>).
Audit: <must-fix-count> must-fix, <should-fix-count> should-fix.
EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths.

### 9d. Push + merge

```sh
git push -u origin pr-4.5-audit-debt-sweep
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-4.5-audit-debt-sweep -m "Integration: merge PR 4.5 (audit-debt-sweep)"
git push origin integration
```

`--no-ff` mandatory.

### 9e. Update trajectory + autonomous log

PLAN.md §2 trajectory: add PR 4.5 row marked `landed on integration` + branch
name. `docs/autonomous_log.md`: append progress entry with timestamp + commit
hash + 13-item delta.

Per continuous-pruning rule: fire a prune agent post-merge to (a) mark the 13
items resolved in `docs/audit_followup_backlog.md`, (b) update
`docs/cross_pr_cleanup_plan.md` §2 to "resolved" state.

---

## 10. Failure modes + recovery

- **10a. PR 5 must-fix 5-M1 not landed.** Pre-flight 6a shows PR 6 merge but no PR 5 lossless-flop guard. STOP. PR 4.5 should not fire until PR 5's must-fix queue is clean.
- **10b. Agent scope expansion.** Agent reports "while reviewing PR 4 audit, I also fixed X." Revert X (out of scope per §3); re-prompt: "Mechanical fixes only; 13 items in §2 are exhaustive."
- **10c. Audit-report line numbers drifted.** Item 3-C says "hunl.py:107, 109" but lines shifted. Agent re-greps for canonical predicate ("raise AssertionError" in `__post_init__`) and patches whichever lines hold it. Items are identified by intent, not literal line number.
- **10d. Cleanup item no longer applicable.** Item 4-B refers to `>= FLOP` predicate that no longer exists (PR 6 rewrote `infoset_key`). Mark RESOLVED in `audit_followup_backlog.md` + reduce §2 scope. Do NOT invent replacement edit.
- **10e. Aggregator test regression on unchanged file.** Flake / order dependency. Re-run with `pytest --co --no-header`; re-run failing test alone. If deterministic, file follow-up; do NOT block PR 4.5 unless failure is in mechanical-fix surface.

---

## 11. Orchestrator decisions needed before fire

1. **Sequencing** (§4): default after PR 5 + PR 6; alternative after PR 5 only (narrow scope to drop 4-C + 4-D + 5-A).
2. **Scope** (§2): default 13 items; user may drop any subset.
3. **License header phrasing** (3-A, 3-B, 4-A): default text per audit reports; user may override.

None blocking. Defaults are spec-aligned per the source audit reports + cross_pr_cleanup_plan §2 + audit_followup_backlog.

---

## 12. Quick-reference paths

- `/Users/ashen/Desktop/poker_solver/docs/cross_pr_cleanup_plan.md` — canonical scope source.
- `/Users/ashen/Desktop/poker_solver/docs/audit_followup_backlog.md` — full backlog.
- `/Users/ashen/Desktop/poker_solver/docs/pr3_prep/audit_report.md` — PR 3 audit (Items 3-A through 3-E).
- `/Users/ashen/Desktop/poker_solver/docs/pr3_5_prep/audit_report.md` — PR 3.5 audit (3.5-A through 3.5-C).
- `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/audit_report.md` — PR 4 audit (4-A through 4-D).
- `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/audit_report.md` — PR 5 audit (5-A).
- `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_report.md` — written by audit agent at §9b (does not exist pre-launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook.
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/tmp/integration_pre_pr_4_5.hash` — reflog backup hash.

Files touched by agents (per §5a):
- `poker_solver/hunl.py` (3-A, 3-C, 3-D, 4-B)
- `poker_solver/action_abstraction.py` (3-B, 3-E)
- `poker_solver/pushfold.py` (3.5-A, 3.5-B, 3.5-C)
- `poker_solver/abstraction/equity_features.py` (4-A)
- `poker_solver/abstraction/emd_clustering.py` (4-C)
- `poker_solver/abstraction/precompute.py` (4-D)
- `poker_solver/profiler/memory.py` (5-A)

Total: 7 source files; ~30-50 LoC delta expected (mostly subtractions + one-line additions). PR diff reviewable in <15 min, not counting audit cross-references.
