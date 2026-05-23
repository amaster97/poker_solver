# Per-PR doc set inventory — 2026-05-22

**Purpose:** verify every PR has the full prep doc set after the `launch_invocations.md` addition. Read-only inventory; no folder contents read.
**Generated:** 2026-05-22 post-`launch_invocations.md` rollout (8 new files).
**Companion to:** `INDEX_2026-05-22.md` (updated in same pass with 8 new `launch_invocations.md` lines).

---

## 1. Canonical doc taxonomy

### 1a. Not-yet-implemented PRs (staged for fan-out)

Standard pack — 9 docs:

1. `prN_spec.md`
2. `agent_a_prompt.md`
3. `agent_b_prompt.md`
4. `agent_c_prompt.md`
5. `audit_prompt.md`
6. `launch_readiness.md` (or `_v2`, `_v3`)
7. `launch_kickoff.md`
8. `fanout_ready.md`
9. `audit_preprep.md`
10. `launch_invocations.md` (NEW — Task tool invocation strings)

(PR 4.5 is a special-case cleanup sweep — no spec, no agent prompts, no audit_prompt; gets the kickoff cluster + invocations.)

### 1b. Implemented / shipped PRs (PR 3, 3.5, 3.5-followup, 4, 5, 6)

Standard pack — 8 docs + audit + commit artifacts:

1. `prN_spec.md`
2. `agent_a_prompt.md` (PR 3 used different patterns pre-canonicalization)
3. `agent_b_prompt.md`
4. `agent_c_prompt.md`
5. `audit_prompt.md`
6. `audit_report.md`
7. `ready_to_commit_summary.md` or `commit_message_draft.md`
8. Various pre-commit checklists / triage / reconciliation as needed

Shipped PRs do not need `launch_invocations.md` (work already done); no retrofit.

---

## 2. Per-PR file counts (raw `ls` count)

| PR | Folder | File count | Status |
|---|---|---|---|
| PR 3 | `pr3_prep/` | 6 | SHIPPED (`a96675c`) |
| PR 3.5 | `pr3_5_prep/` | 4 | SHIPPED (`9f91c83` + `1cbf52a` follow-up) |
| PR 4 | `pr4_prep/` | 10 | SHIPPED (`6565b84`) |
| PR 4.5 | `pr4_5_audit_debt/` | 5 | READY TO COMMIT (no spec / cleanup sweep) |
| PR 5 | `pr5_prep/` | 13 | SHIPPED (`a9d02ca`) |
| PR 6 | `pr6_prep/` | 26 | SHIPPED (`0933367`) — heaviest pack (audit-followup-triage + leduc-timeout + commit-blocked + semver-sequencing artifacts) |
| PR 7 | `pr7_prep/` | 12 | IN FLIGHT (fan-out launched at `6c438b8`) |
| PR 8 | `pr8_prep/` | 10 | STAGED |
| PR 9 | `pr9_prep/` | 10 | STAGED |
| PR 10 (a + b shared) | `pr10_prep/` | 19 | STAGED (a + b combined folder; UI design inputs included) |
| PR 11 | `pr11_prep/` | 10 | STAGED |
| PR 12 | `pr12_prep/` | 10 | STAGED |

**Total prep files across all PR folders:** 135.

---

## 3. Completeness scorecard — staged PRs (9-doc target)

| PR | Spec | A | B | C | Audit prompt | Launch readiness | Launch kickoff | Fanout ready | Audit preprep | Launch invocations | Total | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PR 7 | ✓ | ✓ | ✓ | ✓ | ✓ (×2: base + `_final`) | ✓ | ✓ | ✓ | ✓ | ✓ | 9 + extras | COMPLETE (12 total incl. `noambrown_build_status.md` + `audit_prompt_final.md`) |
| PR 8 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 9 | COMPLETE (10 ÷ folder; same as canon) |
| PR 9 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 9 | COMPLETE |
| PR 10a | ✓ (`pr10a_spec.md` + combined `pr10_spec.md`) | ✓ | ✓ | ✓ | ✓ | n/a (`launch_kickoff_10a.md` doubles) | ✓ | ✓ | ✓ | ✓ | 9 | COMPLETE (3 UI-design inputs + `pr10a_polish_report.md` shared in folder) |
| PR 10b | ✓ (`pr10b_spec.md`) | shared A/B/C w/ 10a | – | – | shared `audit_prompt.md` | – | ✓ | ✓ | ✓ | ✓ | 9 (sharing 3 agent prompts + audit_prompt across split) | COMPLETE |
| PR 11 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 9 | COMPLETE |
| PR 12 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 9 | COMPLETE |

### PR 4.5 (cleanup sweep — reduced pack)
| File | Present |
|---|---|
| `launch_kickoff.md` | ✓ |
| `fanout_ready.md` | ✓ |
| `audit_preprep.md` | ✓ |
| `launch_invocations.md` | ✓ |
| `launch_decision.md` | ✓ |
| Total | 5 (canonical for cleanup sweeps; no spec/prompts needed) |

---

## 4. Completeness scorecard — shipped PRs

| PR | Spec | A | B | C | Audit prompt | Audit report | Commit/ready artifact | Total | Status |
|---|---|---|---|---|---|---|---|---|---|
| PR 3 | ✓ | (legacy: `agent_a_interface_concerns.md`) | – | – | – | ✓ | – | 6 (incl. ref notes) | SHIPPED — pre-canonicalization vintage |
| PR 3.5 | ✓ | – | – | – | ✓ | ✓ | ✓ (`ready_to_commit_summary.md`) | 4 | SHIPPED |
| PR 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ + `launch_alignment_v2.md` + `launch_readiness_report.md` + EMD ref | 10 | SHIPPED — full canonical pack |
| PR 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ + 6 supporting (audit trail / verification / triage / checklists) | 13 | SHIPPED — extensive post-audit cleanup |
| PR 6 | ✓ | ✓ | ✓ | ✓ | ✓ (×2) | ✓ | ✓ + 19 supporting (launch ×3, commit ×6, recon ×3, cross-check ×2, semver / leduc / speedup / etc.) | 26 | SHIPPED — heaviest pack in repo |

**Note:** shipped PRs do **not** get `launch_invocations.md` retrofitted (work already complete; would be archeology, not useful).

---

## 5. INDEX update summary

`INDEX_2026-05-22.md` updated in place with **8 new `launch_invocations.md` lines** under §2a:

| PR | New line added |
|---|---|
| PR 4.5 | `launch_invocations.md` — exact Task tool invocation strings for the 3-agent fan-out |
| PR 7 | `launch_invocations.md` — exact Task tool invocation strings for the 3-agent fan-out |
| PR 8 | `launch_invocations.md` — exact Task tool invocation strings for the 3-agent fan-out |
| PR 9 | `launch_invocations.md` — exact Task tool invocation strings for the 3-agent fan-out |
| PR 10a | `launch_invocations_10a.md` — exact Task tool invocation strings for PR 10a 3-agent fan-out |
| PR 10b | `launch_invocations_10b.md` — exact Task tool invocation strings for PR 10b 3-agent fan-out |
| PR 11 | `launch_invocations.md` — exact Task tool invocation strings for the 3-agent fan-out |
| PR 12 | `launch_invocations.md` — exact Task tool invocation strings for the 3-agent fan-out |

INDEX structure (§1 TL;DR / §2 By topic / §3 By PR readiness / §4 Skim-priority guide) preserved; only additive edits inside the per-PR bullet blocks under §2a.

---

## 6. Gaps + observations

### 6a. No structural gaps

Every staged (not-yet-implemented) PR has the full 9-doc canonical pack including the new `launch_invocations.md`. Every cleanup sweep (PR 4.5) has the 5-doc reduced pack. Every shipped PR has its vintage-appropriate pack.

### 6b. Observations

- **PR 7 has a duplicate audit_prompt** — `audit_prompt.md` + `audit_prompt_final.md`. Same pattern as PR 6. Not a gap; reflects in-flight refinement after fanout review.
- **PR 10 folder is bimodal** — hosts 10a + 10b artifacts side-by-side under `pr10_prep/`. Suffix convention `_10a` / `_10b` distinguishes scoped files (kickoff / fanout / audit_preprep / launch_invocations) from shared files (3 agent prompts, `audit_prompt.md`, 3 UI-design inputs, `pr10a_polish_report.md`). This was an explicit choice; not a gap.
- **PR 10 has no separate `launch_readiness_10a.md` / `_10b.md`** — coverage rolled into the kickoff files. Not flagged as a gap given the split is non-blocking.
- **PR 4.5 has `launch_decision.md`** not present elsewhere — captures the decision to fire 4.5 concurrent with PR 6 / 7. Considered part of the cleanup-sweep pack.
- **PR 6 is the heaviest** at 26 files — reflects the most complex landing (Rust port, multiple launch iterations v2/v3, MUST_PATCH gate, cross-agent reconciliation, leduc timeout fix recipe, semver sequencing). All artifacts retained as a reference for future Rust ports.
- **PR 3 + PR 3.5 are pre-canonicalization vintage** — fewer docs but matched the workflow at the time. No retroactive padding planned.

### 6c. Not gaps (intentional omissions)

- Shipped PRs (3 / 3.5 / 4 / 5 / 6) — no `launch_invocations.md` retrofit. Work already landed.
- PR 4.5 — no spec / agent prompts / audit_prompt. It's a cleanup sweep, not a feature PR. Reduced canonical pack.
- PR 10 — no `launch_readiness_10a.md` / `launch_readiness_10b.md` standalone files; coverage in kickoff files.

---

## 7. Total doc count cross-check

| Bucket | Files |
|---|---|
| PR 3 prep | 6 |
| PR 3.5 prep | 4 |
| PR 4 prep | 10 |
| PR 4.5 audit-debt | 5 |
| PR 5 prep | 13 |
| PR 6 prep | 26 |
| PR 7 prep | 12 |
| PR 8 prep | 10 |
| PR 9 prep | 10 |
| PR 10 prep | 19 |
| PR 11 prep | 10 |
| PR 12 prep | 10 |
| **Sum** | **135 files in per-PR folders** |

INDEX additions: 8 lines (one per staged-PR / cleanup-sweep folder that received `launch_invocations.md`). All 8 files confirmed via `find launch_invocations*`.
