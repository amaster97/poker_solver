# Origin vs Disk Baseline — 2026-05-23

**Purpose.** Inventory exactly what would be pushed if the orchestrator
ran `git push origin main` right now, classify every disk-only file by
push destination (public origin / private mirror / nowhere), and
recommend a commit grouping for the ship agent.

**Mode.** Read-only across all files; only this doc is written.

---

## 1. Origin/main state summary

| Field | Value |
|---|---|
| Public origin tip | `b5777f22f99ee3b912822c0fb30d771dd03954df` (v1.5.1) |
| Local `HEAD` | `dc3df6c93986029e598e61b333d11ecee3a26bcd` (v1.5.0) |
| Tracked files on `origin/main` | 133 |
| Local commits NOT on origin (`origin/main..HEAD`) | 0 |
| Origin commits NOT on local HEAD (`HEAD..origin/main`) | 4 |
| Worktree status | clean (no modified tracked files); 108 untracked entries |

### What origin has that local HEAD lacks (4 commits, fast-forward)

```
b5777f2 v1.5.1: test rigor + docs honesty (engine bundle deferred to v1.5.2)
8b8d181 Honest docs: PR 7 '<10s/spot' claim was aspirational, never validated (see investigation)
5145674 PR 36: profiler test rigor (closed-form toy + calibration + golden-file + structure invariant)
87e0b9a PR 37: equity test-helper for rigorous persona acceptance criteria
```

These four already shipped to public origin and account for the
`tests/_equity_helpers.py`, `tests/conftest.py` re-export,
`tests/test_equity_helpers.py`, `tests/test_memory_profiler.py`
expansion, `tests/test_river_diff_self_sanity.py` comment edit,
`CHANGELOG.md` v1.5.1 entry, and `pyproject.toml` + `__init__.py` version
bumps that exist on origin but not on local HEAD.

**Implication.** Local must `git pull --ff-only origin main` (or
equivalently `git fetch` + `git reset --hard origin/main` if no local
divergent commits) BEFORE creating any new commits, otherwise a push
would either fail (non-fast-forward) or risk clobbering v1.5.1.

### Tracked tree shape on origin/main (categories of the 133 files)

- Root: `.gitignore`, `Cargo.lock`, `Cargo.toml`, `CHANGELOG.md`,
  `CONTRIBUTING.md`, `DEVELOPER.md`, `LICENSE`, `README.md`, `USAGE.md`,
  `pyproject.toml`
- `.github/` issue / PR templates (3 files)
- `assets/` (README + `.icns`)
- `crates/cfr_core/` Rust solver source + bench + 2 tests (~21 files)
- `docs/pr_proposals/v1_5_pr_23_implementer_notes.md` (SINGLE doc on
  origin — everything else under `docs/` is local-only)
- `examples/tiny_csv.csv` (SINGLE example on origin)
- `poker_solver/` Python package (~25 files)
- `scripts/` build / signing / setup (~10 files)
- `tests/` (~40 files, including the 4 v1.5.1 additions)
- `ui/` NiceGUI app (~10 files)

---

## 2. Disk-only files: full inventory + classification

Total untracked entries: **108** (this includes 1 directory expansion;
unique files ≈ 162 markdown + a handful of code/scripts).

Classification key:
- **A — PUBLIC-OK + USER-FACING**: push to `origin/main` (public)
- **B — PUBLIC-OK but INTERNAL-COORDINATION**: push to private mirror
  ONLY (audits, ship plans, retests — per `feedback_public_repo_hygiene`)
- **C — PII / INTERNAL PATHS**: do NOT push anywhere as-is; redact or
  exclude. Hard rule: anything containing `/Users/ashen/`, agent IDs,
  session IDs, or unreleased internal planning artifacts.
- **D — MOVE-OR-DECIDE**: needs a placement decision before push.

### 2a. Class A — PUBLIC-OK + USER-FACING (push to origin)

| File | Lines | PII? | Notes |
|---|---|---|---|
| `docs/aggregator_vs_true_nash_explainer.md` | 206 | clean | Standalone user-facing explainer; references public source files only (`poker_solver/range_aggregator.py:225-301`, `crates/cfr_core/src/lib.rs:428`, `references/code/...` — note: `references/` is gitignored so the reader gets a broken cross-link, but the explainer body still stands on its own). Ready to push as-is. |
| `examples/range_vs_range_river.py` | 158 | clean | Runnable starter example; no PII. Slots cleanly next to `examples/tiny_csv.csv`. Honest framing about v1.0.0 limitations is fine for public audience. |

**Subtotal: 2 files to push to public main (clean as-is).**

Optional 3rd if user approves a README refresh in this ship:
- `docs/README_proposed_update_2026-05-23.md` (510 lines) is a DRAFT
  container, not the final README. The draft's *body* (the fenced
  markdown block) could replace `README.md` (currently stale at v1.0.0
  GA), but per the user's "not flashy" guidance the safer move is to
  defer the README refresh to a separate, deliberate PR.
  **Recommendation: HOLD for ship-agent prompt.**

### 2b. Class B — PUBLIC-OK + INTERNAL-COORDINATION (private mirror only)

These are audit reports, ship plans/reports, retests, integration
notes, diagnostics. Most contain `/Users/ashen/` paths (auto-disqualifies
them from public per `feedback_public_repo_hygiene`); a few are clean
prose but their *content* is internal planning, not user-facing docs.

**Root-level (4 files):**
- `PLAN.md` — strategic plan; contains `/Users/ashen/` paths and
  internal PR/leg numbering. **Class B → private mirror only.**
- `RELEASE_NOTES_2026-05-23.md` — clean of PII but is announcement
  copy, not a repo artifact. **Class D**, see §2d.
- `RELEASE_HEADLINES_2026-05-23.md` — same as above. **Class D.**
- `RELEASE_CHECKLIST_2026-05-23.md` — contains one `/Users/ashen/`
  path (line 14). **Class B → private mirror only** (or redact then
  Class D).

**`docs/` top-level (49 markdown files), all Class B:**

All ship plans, ship reports, audits, comprehensive reviews,
diagnostics, verification reports, hygiene checks, integration reports,
session artifacts. Examples:
- `docs/audit_docs_cross_reference_check.md`
- `docs/autonomous_burst_release_plan.md`
- `docs/brown_apples_to_apples_2026-05-23.md`
- `docs/burst_summary_2026-05-23.md`
- `docs/changelog_consistency_audit.md`
- `docs/comprehensive_review_2026-05-23-{final,late,night,}.md`
- `docs/dcfr_perf_regression_bisection_2026-05-23.md`
- `docs/final_consistency_audit.md`
- `docs/heuristic_judgement_audit_2026-05-23.md`
- `docs/integration_{catchup,cleanup,sequencing_strategy}_*.md`
- `docs/leg{6,9,11..20}_*_ship_{plan,report}.md` (14 files)
- `docs/midsession_hygiene_check.md`
- `docs/persona_test_results/` (20 markdown files)
- `docs/poker_spots_audit_*.md` (3 files)
- `docs/post_{integration_verification_protocol,sync_consistency_check}.md`
- `docs/pr_23_cell_divergence_deep_dive.md`
- `docs/pr_23_deep_cap_algorithmic_triage.md`
- `docs/pr_{29_pr_38,41_pr_42}_private_push_report.md`
- `docs/pr_{38,41,42}_verification_audit.md`
- `docs/pr_39_cherrypick_plan.md`
- `docs/pr_42_repush_report.md`
- `docs/pr_branch_deeper_audit.md`
- `docs/pr10b_prep/`, `docs/pr11_prep/`, `docs/pr13_prep/`,
  `docs/pr15_prep/`, `docs/pr16_prep/`, `docs/pr18_prep/`,
  `docs/pr8_prep/`, `docs/pr8b_prep/`, `docs/pr9_prep/`,
  `docs/pr10a_5_prep/`, `docs/pr21_prep/`, `docs/pr22_prep/`
  (12 directories, ~45 files total)
- `docs/pr_proposals/` (26 markdown files: priya retest scripts, v1_3
  through v1_7 PR proposals + retests + implementer prompts)
- `docs/public_doc_content_audit.md`
- `docs/pytest_pyenv_arch_quirk_2026-05-23.md`
- `docs/README_proposed_update_2026-05-23.md` — DRAFT, see §2a optional
- `docs/release_docs_consistency_check.md`
- `docs/retag_execution_report_2026-05-23.md`
- `docs/river_parity_timeout_investigation_2026-05-23.md`
- `docs/session_shipped_2026-05-23.md`
- `docs/stash_recovery_2026-05-23.md`
- `docs/state_verification_2026-05-23-late.md`
- `docs/strip_and_soften_edits.md`
- `docs/v1_4_3_pre_ship_audit.md`
- `docs/v1_5_0_{brown_acceptance_result,coverage_gap_diagnosis,per_action_divergence_diagnosis,pr_23_audit,release_notes_edit}.md`
- `docs/v1_5_slider_tier_defaults_measured.md`
- `docs/v1_6_1_{bundle_bisection_diagnosis,final_synthesis,staged_acceptance_verification}.md`
- `docs/wake_up_brief_2026-05-23.md`

**Scripts (1 file):**
- `scripts/cleanup_pr_branches.sh` — references internal session
  artifacts (`STATUS.md`, `SESSION_END_FINAL.md`) and audit doc path;
  operational cleanup tool, not a public asset. **Class B → private
  mirror only.**

**Subtotal: ~100 files to push to private mirror only.**

### 2c. Class C — PII / internal paths (do NOT push as-is)

All Class B files that contain `/Users/ashen/` paths fall under the
broader Class C exclusion *for the PUBLIC origin*. Since they are
already filtered to "private mirror only" above, no additional Class C
quarantine bucket is needed for this push wave.

**No PII-leak items found among the four candidate-public files**
(`docs/aggregator_vs_true_nash_explainer.md`,
`examples/range_vs_range_river.py`, `RELEASE_NOTES_2026-05-23.md`,
`RELEASE_HEADLINES_2026-05-23.md`). All four scan clean for
`/Users/ashen/`, session IDs, agent IDs, and `amaster97`.

The `claude_outputs_reference.docx` and `~$claude_outputs_reference.docx`
in the repo root are gitignored via `*.docx` and `~$*` rules — not
candidates for any push.

### 2d. Class D — MOVE-OR-DECIDE (root-level release artifacts)

Three root-level files are PUBLIC-OK in content but unconventional in
location:

| File | Content | Recommended path |
|---|---|---|
| `RELEASE_NOTES_2026-05-23.md` | Comprehensive public release announcement | Either move to `docs/release_notes_v1_5_1.md` and push to public, or leave as the announcement asset and push to private mirror only. **Recommend: private mirror only** (per user's "not flashy" guidance — announcement copy lives in the GitHub release page, not the repo root). |
| `RELEASE_HEADLINES_2026-05-23.md` | Twitter / HN / blog announcement snippets | Same as above — **private mirror only**. |
| `RELEASE_CHECKLIST_2026-05-23.md` | Pre-publication checklist | One `/Users/ashen/` reference at line 14. Either redact + move to `docs/` and push private, or push as-is to private. **Recommend: private mirror only** (operational checklist, internal). |

Net: all three Class D files default to **private mirror only**; the
ship-agent prompt should confirm with the orchestrator if any one of
them needs to go public (e.g., the user explicitly asks for a
`RELEASE_NOTES_v1_5_1.md` at repo root).

---

## 3. Recommended commit grouping (public origin)

After `git pull --ff-only origin main` (fast-forward to `b5777f22`),
two atomic commits cover the public push:

### Commit 1: Add aggregator-vs-true-Nash explainer doc

```
Files added:
- docs/aggregator_vs_true_nash_explainer.md

Suggested subject:
"docs: aggregator vs true-Nash range-vs-range explainer"

Suggested body (short):
"Document the two range-vs-range code paths in poker_solver: the
Pluribus-style per-combo aggregator (solve_range_vs_range, Python)
and the joint vector-form CFR (solve_range_vs_range_rust, PyO3).
Spells out what mathematical object each one solves, when to use
which, and how to interpret divergent outputs. Standalone reference;
no source-code change."
```

### Commit 2: Add range-vs-range river starter example

```
Files added:
- examples/range_vs_range_river.py

Suggested subject:
"examples: runnable river range-vs-range starter"

Suggested body (short):
"Add a runnable single-street river starter example that documents
v1.0.0's hole-card knob shapes (fixed combo vs fixed combo; empty =
full enumeration), points users at the 1326x990 chance-enum
limitation honestly, and shows how to approximate range-vs-range via
combo iteration today. Pairs with docs/aggregator_vs_true_nash_explainer.md."
```

**Rationale for two commits, not one:** each touches a different file
class (`docs/` vs `examples/`); two atomic commits keep `git blame`
clean and let either be reverted independently if needed.

---

## 4. Specific commands the ship agent should run

**Pre-flight (read-only verification):**

```
git -C /Users/ashen/Desktop/poker_solver fetch origin
git -C /Users/ashen/Desktop/poker_solver rev-parse origin/main
# expected: b5777f22f99ee3b912822c0fb30d771dd03954df
git -C /Users/ashen/Desktop/poker_solver log HEAD..origin/main --oneline
# expected: 4 commits (87e0b9a, 5145674, 8b8d181, b5777f2)
```

**Sync local HEAD to origin/main:**

```
git -C /Users/ashen/Desktop/poker_solver pull --ff-only origin main
# verify post-pull HEAD == b5777f22f99ee3b912822c0fb30d771dd03954df
```

**Commit 1 — explainer:**

```
git -C /Users/ashen/Desktop/poker_solver add \
    docs/aggregator_vs_true_nash_explainer.md
git -C /Users/ashen/Desktop/poker_solver commit -m "$(cat <<'EOF'
docs: aggregator vs true-Nash range-vs-range explainer

Document the two range-vs-range code paths in poker_solver: the
Pluribus-style per-combo aggregator (solve_range_vs_range, Python) and
the joint vector-form CFR (solve_range_vs_range_rust, PyO3). Spells out
what mathematical object each one solves, when to use which, and how to
interpret divergent outputs. Standalone reference; no source-code
change.
EOF
)"
```

**Commit 2 — example:**

```
git -C /Users/ashen/Desktop/poker_solver add \
    examples/range_vs_range_river.py
git -C /Users/ashen/Desktop/poker_solver commit -m "$(cat <<'EOF'
examples: runnable river range-vs-range starter

Add a runnable single-street river starter example that documents
v1.0.0's hole-card knob shapes (fixed combo vs fixed combo; empty =
full enumeration), points users at the 1326x990 chance-enum
limitation honestly, and shows how to approximate range-vs-range via
combo iteration today. Pairs with docs/aggregator_vs_true_nash_explainer.md.
EOF
)"
```

**Push to public origin:**

```
git -C /Users/ashen/Desktop/poker_solver push origin main
git -C /Users/ashen/Desktop/poker_solver rev-parse HEAD
# capture for private-mirror sync below
```

**Private-mirror sync (separate channel — Class B files):**

The orchestrator should NOT bundle Class B / D into the public push.
Use the dual-remote protocol (`feedback_dual_remote_workflow`) to push
the PLAN.md update, ship reports, audits, retest results, and release
artifacts to `backup` on a separate integration branch — those are out
of scope for this baseline doc but flagged here for hand-off.

---

## 5. Hard rules respected

- READ-ONLY across all 162+ markdown files inspected
- WRITE confined to this single doc:
  `/Users/ashen/Desktop/poker_solver/docs/origin_vs_disk_baseline.md`
- NO commits, pushes, tags, or file modifications performed
- Time budget: well under 10 min

---

## 6. Summary numbers

- Files to push to **public main** in this wave: **2**
  (`docs/aggregator_vs_true_nash_explainer.md`,
  `examples/range_vs_range_river.py`)
- Files going to **private mirror only**: **~100**
  (1 root PLAN.md + 3 root release artifacts + ~95 docs/ files +
  1 script)
- **PII leaks found in candidate-public files: 0**
- PII / internal paths present in private-mirror files: many
  (acceptable; private mirror is the intended destination)

