# LEG 21 — v1.6.1 Engine-Only Ship Plan (Path D)

**Date staged:** 2026-05-23 (late)
**Status:** **PRE-STAGED — execution BLOCKED pending user sign-off on `docs/v1_6_1_path_d_decision.md`**
**Supersedes:** `docs/leg19_v1_6_1_ship_plan_REVISED.md` (which assumed a closable strict gate)
**Filename:** `docs/leg21_v1_6_1_engine_only_ship_plan.md`

---

## 0. WHAT THIS PLAN ASSUMES

The user has approved **Path D** from `docs/v1_6_1_path_d_decision.md`:

> Ship engine improvements (PR 33 + PR 46 + PR 40 + PR 35c) as v1.6.1 WITHOUT the strict Brown apples-to-apples acceptance gate. Mark the gate as `xfail` with a documented explanation. Resume Gate 4 + v1.7.0 + .dmg release momentum afterward.

If Path D is NOT approved, this plan is moot — fall back to `docs/v1_6_1_path_d_decision.md` §5 (Path B redefine-gate alternative) and re-stage a new plan.

---

## 1. Bundle composition

> **Branches bundled (cherry-pick order):**
>
> 1. **PR 46** `pr-46-dcfr-panic-fix` @ `cd56761` — Rust off-by-one panic fix in `dcfr_vector.rs:651`. CLEAN.
> 2. **PR 33** `pr-33-python-delegate` @ `29a00c0` — Python auto-delegate to Rust vector-form CFR. CLEAN.
> 3. **PR 35c** `pr-35c-paired-fix` @ `63c9432` — paired ALL_IN cap-guard in Rust `hunl.rs` + Python `action_abstraction.py`. CLEAN.
> 4. **PR 40** `pr-40-acceptance-test-fix` @ `c058e97` — action permutation + range-slot fixes. ONE EXPECTED CONFLICT at `PER_ACTION_TOL` line (resolve per dry-run #2 §1).
> 5. **(Path D delta)** New commit on top: `xfail` the strict Brown apples-to-apples gate with documented reason.
>
> **NOT IN THE v1.6.1 BUNDLE:**
> - PR 35d Brown quirk doc — defer to v1.6.2 or fold into the xfail reason text inline.
> - PR 47 phantom-ALL_IN fix — defer. Optional inclusion only if pre-ship investigation confirms a real guard gap; otherwise hold for v1.6.2.

**Bump:** PATCH (1.6.0 → 1.6.1).
**Reason:** P0 panic fix + backwards-compatible auto-delegate + paired cap-guard + test plumbing. No new user-visible features. Semver PATCH is the correct slot.

---

## 2. Pre-ship verification (must pass before commit)

Run from `/Users/ashen/Desktop/poker_solver` on a disposable worktree (NEVER on main working tree per `feedback_no_concurrent_branch_ops.md`):

```bash
# 1. Create worktree
git worktree add /tmp/v1_6_1_leg21_ship origin/main

cd /tmp/v1_6_1_leg21_ship

# 2. Cherry-pick in order
git cherry-pick cd56761  # PR 46
git cherry-pick 29a00c0  # PR 33
git cherry-pick 63c9432  # PR 35c
git cherry-pick c058e97  # PR 40  (expect conflict at PER_ACTION_TOL; resolve to 5e-2 with xfail reason comment)

# 3. Apply Path D delta: xfail the strict gate
# Edit tests/test_v1_5_brown_apples_to_apples.py:
#   Add @pytest.mark.xfail(reason="...") on test_v1_5_brown_apples_to_apples_parity
#   reason text must cite docs/a83_deep_cap_root_cause_investigation.md
git add tests/test_v1_5_brown_apples_to_apples.py
git commit -m "v1.6.1: xfail Brown apples-to-apples per-action gate (Path D)"

# 4. Build + unit tests
cargo build --release
cargo test --release --lib  # expect 50/50 PASS
cargo test --release --test hunl_state_unit  # expect 19/19 PASS

# 5. Maturin develop
maturin develop --release  # rebuild Python bindings

# 6. Critical Python-Rust regression gate
pytest tests/test_exploit_diff.py -v  # expect 5/5 PASS

# 7. Python tier smoke
pytest tests/test_python_delegate.py -v  # expect PASS (PR 33 verification)

# 8. Brown apples-to-apples (xfailed; should report xfail not fail)
pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=900
# Expected output: "xfailed" status, not "failed"; STRICT_RESULT printed for monitoring
```

**Pass criteria (all must hold):**

- [ ] All cherry-picks land cleanly (one expected conflict at PR 40)
- [ ] `cargo test --lib` 50/50 PASS
- [ ] `cargo test --test hunl_state_unit` 19/19 PASS
- [ ] `maturin develop --release` builds successfully
- [ ] `pytest tests/test_exploit_diff.py` 5/5 PASS (critical gate)
- [ ] `pytest tests/test_python_delegate.py` PASS (PR 33 gate)
- [ ] `pytest tests/test_v1_5_brown_apples_to_apples.py` reports `xfailed`, NOT `failed`
- [ ] No new test failures introduced beyond the documented xfail

If ANY of these fail, **STOP and report.** Do not proceed to push.

---

## 3. Smoke matrix

Run after pre-ship verification PASSes, before tagging:

| Test | Command | Expected | Source-of-truth |
|---|---|---|---|
| Rust lib | `cargo test --release --lib` | 50/50 PASS | dry-run #2 §2b |
| Rust HUNL state | `cargo test --release --test hunl_state_unit` | 19/19 PASS | dry-run #2 §2b |
| Python-Rust diff | `pytest tests/test_exploit_diff.py` | 5/5 PASS | PR 35c report |
| Python delegate | `pytest tests/test_python_delegate.py` | PASS | PR 33 report |
| Range-vs-range diff | `pytest tests/test_range_vs_range_rust_diff.py` | PASS | Internal validation; not affected by Brown gate |
| Brown apples-to-apples | `pytest tests/test_v1_5_brown_apples_to_apples.py` | XFAILED (with STRICT_RESULT monitoring output) | Path D delta |
| Engine perf smoke | `pytest tests/test_perf_smoke.py` (if exists) | PASS within Marcus persona budget | `feedback_persona_time_budgets.md` |

**The Brown gate is `xfail` — the test still runs and reports the residual, but does not fail CI.** This preserves it as a monitoring signal for future engine work without blocking ship.

---

## 4. CHANGELOG entry

Add to `CHANGELOG.md` at the top:

```markdown
## v1.6.1 — 2026-05-XX

### Fixed
- P0 off-by-one panic in `dcfr_vector.rs:651` affecting `traverse` on certain
  deep histories (was-PR-34, never merged to public origin until now).
- Paired ALL_IN cap-guard in `hunl.rs` (Rust) and `action_abstraction.py`
  (Python) — both engines now skip ALL_IN at cap to match the canonical
  action set.
- Brown apples-to-apples acceptance test plumbing (action permutation,
  range-to-player-slot mapping).

### Added
- Python auto-delegate to Rust vector-form CFR when `initial_hole_cards=()`
  is passed to `HUNLSolver`; ~3-5x speedup on range-vs-range queries
  (no behavior change for non-delegating calls).

### Known limitations
- The strict per-action probability match in
  `test_v1_5_brown_apples_to_apples_parity` is currently marked `xfail`
  pending resolution of a documented terminal-utility convention divergence
  between our zero-sum game and Brown's `base_pot`-inclusive game. See
  `docs/a83_deep_cap_root_cause_investigation.md` for the full analysis.
  Structural parity (action-count match across histories, ≥80% coverage)
  PASSes; only the strict per-cell probability tolerance is deferred.
```

---

## 5. Push gate

**Push order (after smoke matrix all PASS):**

1. **Squash-merge the worktree** onto a new branch `release-v1.6.1` on local repo.
2. **Push to private mirror** first: `git push private release-v1.6.1`.
3. **Audit content** (per `feedback_public_repo_hygiene.md`):
   - [ ] No internal session IDs in commit messages or test output
   - [ ] No PII or internal planning notes in CHANGELOG
   - [ ] No xfail reason text leaking internal investigation details (links to public docs only, or to docs that have been promoted to public-safe via separate audit)
4. **Decision point: is `docs/a83_deep_cap_root_cause_investigation.md` public-safe?**
   - If YES → reference it directly in the xfail reason.
   - If NO → write a sanitized public version first (defer ship until done), OR use a generic reason text like "pending terminal-utility convention review; see internal investigation."
5. **Push to public origin/main:** `git push origin main` (after merge to main).
6. **Tag:** `git tag v1.6.1 && git push origin v1.6.1 && git push private v1.6.1`.

**HARD GATES before public push:**
- [ ] User has explicitly approved Path D on session sign-on
- [ ] Smoke matrix all PASS
- [ ] Content audit complete
- [ ] No outstanding investigation that would change v1.6.1 composition

**NEVER:**
- [ ] Force-push to main
- [ ] Skip hooks (`--no-verify`)
- [ ] Delete the xfail mark "to make CI green" — the xfail IS the documented state

---

## 6. Post-ship cascading work

After v1.6.1 lands:

1. **GitHub Release** — draft notes from CHANGELOG; pin to `v1.6.1` tag; publish.
2. **Private mirror sync verification** — run post-integration verification protocol per `feedback_post_integration_verification.md` to catch routing drift.
3. **Resume Gate 4 (200K-iter exploitability)** — schedule the long-running validation that was queued before the v1.6.1 detour.
4. **Resume Gate 5 (.dmg release)** — PR 11 rebuild + smoke verification per `feedback_ui_packaging_sync.md`.
5. **Queue v1.6.2 design** — three candidates to triage with user:
   - Convention surgery (modify `terminal_utility` to include `base_pot`) — multi-week, high risk
   - Restructure Brown gate as structural-parity with WARN/FAIL bands (Path B applied post-1.6.1)
   - Phantom-ALL_IN guard (PR 47) — small-scope cleanup; may not move the gate but improves structural parity

---

## 7. Rollback if v1.6.1 ships and something breaks

1. **Revert tag and main pointer:** `git revert <merge-sha>` on main; force-push NOT used (warn user before any force operation).
2. **Re-tag main without v1.6.1:** delete tag locally + on origin + private; replace with `v1.6.0` as latest.
3. **File post-mortem** under `docs/postmortem_v1_6_1_rollback.md` if invoked.

Most likely failure modes:
- Maturin build pinning issue on user systems — covered by .dmg artifact (PR 11), not by source ship
- PR 33 delegate edge case not caught in pre-ship — would manifest as `test_python_delegate.py` regression in user CI
- PR 35c cap-guard regresses `test_exploit_diff` on a non-tested combo — would require holding ship until covered

---

## 8. Constraints honored on this plan

- [x] No code modified — pure planning pass
- [x] No commit; no push; no merge
- [x] No sub-agents spawned
- [x] Within 20-min time budget for plan-stub authoring
- [x] Awaits user sign-off on `docs/v1_6_1_path_d_decision.md` before any execution

---

## 9. Source-of-truth pointers

- This plan: `/Users/ashen/Desktop/poker_solver/docs/leg21_v1_6_1_engine_only_ship_plan.md`
- Path D decision doc (must approve first): `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_path_d_decision.md`
- Dry-run #2 evidence: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_attempt_2.md`
- Root-cause investigation: `/Users/ashen/Desktop/poker_solver/docs/a83_deep_cap_root_cause_investigation.md`
- Superseded prior plan: `/Users/ashen/Desktop/poker_solver/docs/leg19_v1_6_1_ship_plan_REVISED.md`
- PR 35c report: `/Users/ashen/Desktop/poker_solver/docs/pr_35c_paired_fix_report.md`
- PR 46 report: `/Users/ashen/Desktop/poker_solver/docs/pr_46_dcfr_panic_fix_report.md`
- Persona budget framework: `feedback_persona_time_budgets.md` (Marcus is gating)
- Public repo hygiene: `feedback_public_repo_hygiene.md`
