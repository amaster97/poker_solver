# PR 7 commit pipeline readiness (pre-flight check)

**Date:** 2026-05-22
**Mode:** Read-only verification pass. No commands executed; no files touched outside this report.
**Verdict at write time:** GREEN on prep gates, AMBER on audit (in flight), GO-PENDING on commit.

---

## 1. Pre-flight gates status

| Gate | Status | Anchor |
|------|--------|--------|
| Branch verified `pr-7-noambrown-diff` | GREEN | `agent_progress_check.md:4`, `audit_prompt_final.md:18` |
| Integration tip is post-PR-6 (`6c438b8`) | GREEN (assumed, untested per read-only rule) | `audit_prompt_final.md:18` (branched from `integration`) |
| All 3 agents reported back (A + B + C) | GREEN | `agent_progress_check.md:9-49` lists files from all three; no empty stubs |
| Parity-module sanity audit | GREEN (clean) | `parity_module_audit.md:96`: "No blocking concerns. PR 7 commit can proceed; items 1-4 are polish." |
| Pre-prep forecast doc available | GREEN | `audit_preprep.md:101` forecast: READY-WITH-PATCHES ~55%, clean READY ~30%, NOT-READY ~15% |
| Audit prompt final (15 focus areas) staged | GREEN | `audit_prompt_final.md:42-156` enumerates all 15 focus areas with file:line evidence stubs |
| Audit report `audit_report.md` | PENDING (in flight) | File does not yet exist at `docs/pr7_prep/audit_report.md` |
| Commit message draft `commit_message_draft.md` | GREEN (landed since the kickoff of this preflight) | File exists, 9.1 KB; opens with title "PR 7: River-spot diff vs Brown's MIT solver (external Nash validation) (v0.5.1)" |

**Net:** 7 of 8 gates green; one (the audit report itself) is the gating artifact that the rest of the pipeline waits on. Commit message draft moved from PENDING to GREEN during this preflight.

---

## 2. Expected commit scope

Per `agent_progress_check.md` §4 (LOC summary):

- **~2,076 LOC new across 7 new files** (+ 2 modified) — orchestrator's "~2,076 LOC across 8 files" framing aligns within rounding (counting the `pyproject.toml` marker bump + `tests/test_hunl_diff.py` hardening as the 8th touch point with the 7 untracked-tree new files).
- **New files (Agent A + B + C):**
  - `poker_solver/parity/__init__.py` (21 LOC)
  - `poker_solver/parity/noambrown_wrapper.py` (1,217 LOC)
  - `scripts/build_noambrown.sh` (69 LOC, +x)
  - `tests/data/river_spots.json` (25.8 KB, 15 spots, schema_version=1)
  - `tests/test_river_diff.py` (491 LOC)
  - `tests/test_river_diff_self_sanity.py` (278 LOC)
- **Modified files:**
  - `pyproject.toml` (+1 line: `parity_noambrown` marker registration)
  - `tests/test_hunl_diff.py` (+21 / -6: hardened PR 6 import error to RuntimeError)
- **Plus the v0.5.1 release bundle** (per `commit_message_draft.md:27-33`): `poker_solver/__init__.py` version bump, `pyproject.toml` `[project] version` bump, `CHANGELOG.md` new `[0.5.1]` section, `README.md` "Current version" line.

**License compliance:** Brown's MIT, invoke-only (subprocess + JSON), no C++ source copied. Confirmed in `parity_module_audit.md:74-83` and the wrapper docstring per `audit_prompt_final.md:103-109`.

---

## 3. Sequencing once audit + commit message both land

1. **Read `audit_report.md`** — gate on verdict line. If "READY for commit" or "READY for commit AFTER must-fix items resolved" with patches the user accepts → proceed. If "NOT READY" → halt, escalate.
2. **Apply must-fix patches** (if any) via fresh agents — most likely surfaces per `audit_preprep.md` §1: raise canonicalization (§1.3, case 8), xdist `/tmp` collision (§1.4), or build script soft-fail edge cases (§1.7).
3. **Re-trigger pytest** on the patched files only (targeted, not full suite).
4. **Fire commit pipeline (sequential, in order):**
   a. `cargo build --release` (PR 6 lesson: Rust still gates the release binary).
   b. `cargo test` (targeted to the parity-adjacent crate paths if scoping is supported).
   c. `pytest -m "not parity_noambrown" tests/` (avoid the 30-90s Brown invocation in the main lane unless Brown binary is built).
   d. `pytest tests/test_river_diff_self_sanity.py` (always-runs, Brown-free, fast).
   e. `git add` the 7 new files + 2 modified + 4 release-bundle files (see §2).
   f. `git commit` using `commit_message_draft.md` as the HEREDOC body.
   g. `git push -u origin pr-7-noambrown-diff`.
   h. Merge into `integration` after gh checks pass (or fast-forward locally then push).
5. **Tag `v0.5.1`** after merge tip is on `integration`.
6. **6-branch sync** (see §5).

---

## 4. Risks before commit

- **PR 6 lesson — full pytest is slow.** Per `feedback_no_extrapolate.md` and the PR 6 retrospective, the full suite can take 8-15 min when the Rust extension is freshly rebuilt. Mitigation: targeted pytest only on `tests/test_river_diff*.py` + `tests/test_hunl_diff.py` for the pre-commit gate; defer full-suite to post-merge CI.
- **Expected audit verdict — READY-WITH-PATCHES (~55% prior).** Per `audit_preprep.md:113`: probability mass favors must-fix patches landing. Build a contingency for 1-2 small fixes between audit landing and the commit push. The most-likely patch surfaces (in descending order of prior probability):
  1. Raise canonicalization round-trip case 8 (`b500/r9000 ↔ b500A`) — `audit_preprep.md` §1.3.
  2. `tempfile.NamedTemporaryFile(suffix=".json", delete=False)` versus a deterministic `/tmp/spot_<id>.json` — `audit_preprep.md` §1.4.
  3. Build script soft-fail edge cases on missing Xcode CLT (`set -e` interaction) — `audit_preprep.md` §1.7.
- **`HistoryRoot` not in `__all__`.** Per `parity_module_audit.md:90`: cosmetic but the audit may flag as should-fix. Tiny patch (add to `__all__` or prefix with underscore).
- **Note A from progress check.** `tests/fixtures/river_diff_fixtures.py` not produced; fixture lives as raw JSON at `tests/data/river_spots.json`. Per `agent_progress_check.md:63-65` this is a structural deviation, arguably cleaner, but the audit may call it out as a should-fix (deviation from spec).
- **Stale `.so` hard-fail (PR 6 carry-over).** `tests/test_hunl_diff.py` was modified to harden the PR 6 import error to `RuntimeError`. Confirm this change is what the diff actually contains before committing — could trip the audit's "scope creep" radar if the audit considers it out of PR 7's blast radius.
- **CHANGELOG / README / version-bump consistency.** Per `commit_message_draft.md:27-33` the v0.5.1 release bundle is included in this commit. Verify those four files are actually edited before staging (they were not in the `agent_progress_check.md` file list — they may be a separate orchestrator side-deliverable, or may still need to be applied).

---

## 5. 6-branch sync verification post-merge

Per `feedback_pr_branches.md` (per-PR branches from PR 3+) and the project's branch topology, the post-merge sync sequence is:

1. Confirm `pr-7-noambrown-diff` is merged into `integration` (the named tip).
2. Verify each of the other 5 active branches has rebased or fast-merged the new `integration` tip — typical branch family is `main`, `integration`, `pr-7-noambrown-diff`, plus PR 8/9 spike branches if active.
3. Spot-check for ahead/behind divergence on each branch:
   - `git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads/`
4. Resolve any branch left "behind" by `integration` after merge — typically by rebase, never by force-push to main per `feedback_no_concurrent_branch_ops.md`.
5. Tag `v0.5.1` on the `integration` tip after sync; push the tag.

**Constraint reminder (per `feedback_no_concurrent_branch_ops.md`):** no branch switching in the shared working tree while other agents may write. Use `git worktree add` for any post-merge sync work that runs in parallel with PR 8 / PR 9 agents.

---

## Anchors

- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt_final.md`
- Audit pre-prep + forecast: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_preprep.md`
- Agent progress snapshot: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_progress_check.md`
- Parity module sanity audit: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/parity_module_audit.md`
- Commit message draft: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/commit_message_draft.md`
- Audit report (expected): `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_report.md` (pending)
