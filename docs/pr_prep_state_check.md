# PR 7 + 8 + 9 fan-out prep state check

**Date:** 2026-05-22
**Status:** Read-only audit of `docs/pr{7,8,9}_prep/` to verify fan-out readiness.
**Verdict:** PR 7 is in flight (Agents A/B/C launched ~03:50 UTC per `launch_invocations.md`); PR 8 and PR 9 fan-out-ready when their gates clear.

---

## 1. Required-file matrix

Legend: `OK` = present + non-empty (≥ ~50 lines or evidently substantive); `MISSING` = file absent.

### PR 7 (`docs/pr7_prep/`)

| File                  | Present | Lines | Status |
|-----------------------|---------|-------|--------|
| `pr7_spec.md`         | yes     | 306   | OK     |
| `agent_a_prompt.md`   | yes     | 576   | OK     |
| `agent_b_prompt.md`   | yes     | 347   | OK     |
| `agent_c_prompt.md`   | yes     | 340   | OK     |
| `audit_prompt.md`     | yes     | 189   | OK     |
| `launch_kickoff.md`   | yes     | 349   | OK     |
| `launch_readiness.md` | yes     | 69    | OK (compact gate doc; expected) |
| `fanout_ready.md`     | yes     | 129   | OK     |
| `audit_preprep.md`    | yes     | 143   | OK     |

**Extras present:** `launch_invocations.md` (165 lines — concrete fan-out invocations, dated 22 May 03:50 — corroborates "in flight"), `noambrown_build_status.md` (91 lines — reference build status).

**Coverage gap:** none. All seven required artefacts present and substantive.

---

### PR 8 (`docs/pr8_prep/`)

| File                  | Present | Lines | Status |
|-----------------------|---------|-------|--------|
| `pr8_spec.md`         | yes     | 504   | OK     |
| `agent_a_prompt.md`   | yes     | 376   | OK     |
| `agent_b_prompt.md`   | yes     | 585   | OK     |
| `agent_c_prompt.md`   | yes     | 481   | OK     |
| `audit_prompt.md`     | yes     | 177   | OK     |
| `launch_kickoff.md`   | yes     | 352   | OK     |
| `launch_readiness.md` | yes     | 101   | OK     |
| `fanout_ready.md`     | yes     | 147   | OK     |
| `audit_preprep.md`    | yes     | 188   | OK     |

**Coverage gap:** none. All seven required artefacts present and substantive. No `launch_invocations.md` yet — expected (PR 8 not in flight).

---

### PR 9 (`docs/pr9_prep/`)

| File                  | Present | Lines | Status |
|-----------------------|---------|-------|--------|
| `pr9_spec.md`         | yes     | 581   | OK     |
| `agent_a_prompt.md`   | yes     | 615   | OK     |
| `agent_b_prompt.md`   | yes     | 440   | OK     |
| `agent_c_prompt.md`   | yes     | 486   | OK     |
| `audit_prompt.md`     | yes     | 198   | OK     |
| `launch_kickoff.md`   | yes     | 368   | OK     |
| `launch_readiness.md` | yes     | 129   | OK     |
| `fanout_ready.md`     | yes     | 116   | OK     |
| `audit_preprep.md`    | yes     | 184   | OK     |

**Coverage gap:** none. All seven required artefacts present and substantive. No `launch_invocations.md` yet — expected (PR 9 not in flight; gated on PR 5+6+ideally-7).

---

## 2. PR 9 `on_progress` consistency check

Per the earlier launch-readiness patch round, `on_progress: Callable[[int, float, MemoryReport], None] | None = None` must appear consistently across PR 9's spec + all three agent prompts + audit prompt.

| File                                | `on_progress` mentions | Threading documented | Status |
|-------------------------------------|------------------------|----------------------|--------|
| `pr9_spec.md`                       | 5 (lines 131, 132, 137, 138, 143-144) | yes — across `solve_hunl_preflop`, `build_blueprint`, `refine_subgame` | OK |
| `agent_a_prompt.md` (Python surface)| 6 (lines 76, 132, 171, 241, 264, 615) | yes — threaded through `solve_hunl_preflop` → `build_blueprint` AND → `refine_subgame` (cite required in deliverable item 8) | OK |
| `agent_b_prompt.md` (subgame refine)| 6 (lines 65, 137, 167, 171, 189, 440)  | yes — `refine_subgame` → PR 5's `solve_hunl_postflop`, or direct DCFRSolver invocation | OK |
| `agent_c_prompt.md` (Rust port)     | 6 (lines 84, 265, 271, 276, 279, 486)  | yes — Rust accepts `Option<PyObject>`, invokes via `Python::with_gil`; deliverable item 10 mandates citation | OK |
| `audit_prompt.md`                   | 4 (lines 130, 131, 133, 137, 185)      | yes — must-fix gate explicit: "missing from any of the three entrypoints OR silently dropped" blocks PR | OK |

**Signature uniformity:** all five files agree on `Callable[[int, float, MemoryReport], None] | None = None`, invocation cadence (`every log_every iterations`), payload (`(iteration_number, current_exploitability_bb, memory_snapshot)`), and the cancellation carve-out ("Cancellation NOT in this contract — UI cancellation flows through a separate flag per PR 10a design").

**Consumer pin:** all five files cite the downstream consumer at `docs/pr10_prep/pr10b_spec.md` lines 152-156.

**Verdict:** `on_progress` is consistent across the spec + all three agent prompts + audit prompt. Patch round closed cleanly.

---

## 3. Coverage gaps (cross-PR)

| Concern | PR 7 | PR 8 | PR 9 |
|---------|------|------|------|
| Spec present? | yes | yes | yes |
| All three agent prompts present? | yes | yes | yes |
| Audit prompt present? | yes | yes | yes |
| Launch kickoff present? | yes | yes | yes |
| Launch readiness gate doc present? | yes | yes | yes |
| Fan-out-ready signal doc present? | yes | yes | yes |
| Audit pre-prep (anticipated findings) present? | yes | yes | yes |
| Concrete fan-out invocations recorded? | yes (`launch_invocations.md` 22 May 03:50) | n/a (not in flight) | n/a (not in flight) |

**No coverage gaps identified.** Every PR has its full seven-artefact bundle. PR 7 additionally has post-fan-out launch invocations recorded.

---

## 4. Verdict

- **PR 7:** in flight. Agents A/B/C launched per `docs/pr7_prep/launch_invocations.md` (22 May 03:50). All upstream artefacts in place; audit pre-prep loaded for the post-implementation audit agent.
- **PR 8:** fan-out-ready. All seven artefacts present + non-trivial. Awaits gate clear (per `launch_readiness.md` + `fanout_ready.md` — "PR 6 on integration AND user explicit approval").
- **PR 9:** fan-out-ready. All seven artefacts present + non-trivial. `on_progress` launch-readiness patch is consistent across spec, all three agent prompts, and audit prompt. Awaits gate clear (per `fanout_ready.md` — "PR 5 + PR 6 on integration, ideally PR 7 too for external Nash validation").

**Biggest gap:** none. Prep state is clean across all three PRs.

---

## 5. Notes / non-blocking observations

- PR 7 `launch_readiness.md` is the shortest (69 lines) but is a focused gate doc rather than a content artefact — content is in `launch_kickoff.md` (349 lines) and `fanout_ready.md` (129 lines). No remediation needed.
- PR 7 has an extra `noambrown_build_status.md` (91 lines) tracking the reference-build dependency. Not required by the audit template but useful context.
- PR 8's `pr8_spec.md` (504 lines) and PR 9's `pr9_spec.md` (581 lines) are the largest specs — consistent with the scope of those fan-outs (PR 9 owns ~1,300 Rust LOC + ~600 Python LOC + ~600 test LOC per its `fanout_ready.md`).
- Total prep corpus: 8,732 lines across 28 files.
