# Integration Sequencing Strategy

**Date:** 2026-05-23 (end-of-day burst session)
**Scope:** Coordinate landing of five in-flight tracks against integration without textual or semantic collision.
**Status:** Integration-only document (private channel; not published to public `origin/main`).

---

## 1. Current state snapshot

**Integration tip:** `0ea83e1` (v1.3.0 — range-vs-range API via blueprint aggregator). **Main tip:** `58b1ebd` (same v1.3.0 release; parallel history post Option C split). **Today's ship sequence:** v1.0.1 → v1.1.0 → v1.2.0 → v1.2.1 → v1.3.0.

**Five tracks currently in flight:**

| Track | Branch | Working tree | Target |
|---|---|---|---|
| PR 15 — Option A (Rust exploit port) | `pr-15-rvr-perf` | mods `crates/cfr_core/src/{hunl.rs,lib.rs}` + `poker_solver/solver.py`; new `exploit.rs` + `tests/test_exploit_diff.py` | v1.3.2 (obviated by PR 17) |
| PR 17 — Plan C (dense slabs, true Nash) | `pr-17-plan-c-dense-slabs` | mods `crates/cfr_core/src/lib.rs` + `poker_solver/solver.py`; new `exploit_vec.rs` + `tests/test_exploitability_diff_vec.py` | v1.3.2 or v1.4.0 |
| PR 19 — v0.6.2 UI fixes | `pr-19-v062-small-fixes` | mods `ui/state.py` + `ui/views/run_panel.py` | v1.3.1 (bundle w/ PR 20) |
| PR 20 — aggregator patch | `pr-20-v131-aggregator-patch` | mods `poker_solver/range_aggregator.py` | v1.3.1 (bundle w/ PR 19) |
| PR 21 — Node-locking | (spec; branch not cut) | will mod `poker_solver/{dcfr.py,solver.py}` + `crates/cfr_core/src/dcfr.rs` | v1.4.0 |

---

## 2. File-level overlap analysis

- **`CHANGELOG.md`** — touched by every ship; serializes by construction (each cherry-pick adds its entry above the previous).
- **`pyproject.toml`** + **`poker_solver/__init__.py`** — every ship bumps `__version__`; must serialize (semver tags collide otherwise).
- **`crates/cfr_core/src/exploit*.rs`** — PR 15 creates `exploit.rs`; PR 17 creates `exploit_vec.rs`. Different filenames; **semantic overlap is high even though textual overlap is low** (both port the Python exploitability walk).
- **`crates/cfr_core/src/lib.rs`** — PR 15 and PR 17 both add PyO3 module exports; **textual conflict on register lines is likely**.
- **`poker_solver/solver.py`** — PR 15 wires Option A; PR 17 wires Plan C; PR 21 adds `locked_strategies` parameter. **Three-way potential.**
- **`poker_solver/range_aggregator.py`** — only PR 20. No conflict.
- **`ui/state.py` + `ui/views/run_panel.py`** — only PR 19. No conflict.
- **`crates/cfr_core/src/dcfr.rs`** — only PR 21. No conflict.
- **`crates/cfr_core/src/hunl.rs`** — only PR 15. No conflict.

---

## 3. Conflict matrix

Pairwise likelihood of cherry-pick conflicts when landing the second of each pair:

| | PR 15 | PR 17 | PR 19 | PR 20 | PR 21 |
|---|---|---|---|---|---|
| **PR 15** | — | likely (lib.rs + solver.py + semantic redundancy) | unlikely | unlikely | possible (solver.py textual; semantic disjoint) |
| **PR 17** | likely | — | unlikely | unlikely | possible (solver.py textual; semantic disjoint) |
| **PR 19** | unlikely | unlikely | — | unlikely (CHANGELOG + version only) | unlikely |
| **PR 20** | unlikely | unlikely | unlikely | — | unlikely |
| **PR 21** | possible | possible | unlikely | unlikely | — |

**Inevitable serial collisions** (CHANGELOG top entry, pyproject version, `__init__.py` version) are sequence points by design, not dangerous conflicts.

---

## 4. Ship sequence recommendation

1. **v1.3.1 = PR 19 + PR 20 bundled.** Both touch disjoint files from everything else. Cleanest first ship. **Bundle** because (a) both are small follow-up patches, (b) disjoint surfaces inside the bundle (range_aggregator vs ui/), (c) two separate releases would mean two version bumps for one cleanup pass. Single CHANGELOG entry: "v1.3.1 — aggregator patch + v0.6.2 UI fixes."

2. **v1.3.2 or v1.4.0 = PR 17 (Plan C).** If Plan C lands clean at the perf gate, it is the true-Nash path and supersedes PR 15. **Decision rule:** if both 15 and 17 are audit-clear, ship 17 only; annotate PR 15 as superseded.

3. **PR 15 ships ONLY IF PR 17 does not land clean.** Option A is a perf path without true Nash; redundant if Plan C lands. If Plan C blocks, PR 15 takes v1.3.2 and PR 17 becomes v1.4.0 follow-up.

4. **v1.4.0 = PR 21 (node-locking).** Bigger surface (`dcfr.py` + `dcfr.rs` + `solver.py`); touches the regret-update path, so Type B risk is non-trivial. Ship last so it rebases onto a stable v1.3.x tip.

5. **PR 22 (.dmg repackage) → fires after v1.3.x cleanup.** Smoke-tests universal2 + new exploitability binaries together.

---

## 5. Conflict resolution playbook

- **PR 15 vs PR 17** on `lib.rs` + `solver.py`: same module-registration lines, same wiring point. **Resolution:** if Plan C lands clean, OBVIATE PR 15 (annotate "Superseded by PR 17; closed without merge"). If Plan C does not land clean, PR 15 ships as fallback perf path.
- **PR 15/17 vs PR 21** on `solver.py`: PR 21 adds `locked_strategies` parameter; PR 15/17 modifies BR walk. **Semantically disjoint** (plumbing vs walk logic); textual cherry-pick conflict possible. **Resolution:** rebase PR 21 onto whatever exploit path lands; resolve parameter hunks manually. Estimated 5-30 lines; no semantic merge.
- **CHANGELOG + version files** on every ship: sequence point, not conflict.
- **Persona phase surfaces Type B mid-ship:** classify per `docs/rectification_framework.md`. Fix in place, ship as `vX.Y.(Z+1)` PATCH; do not roll back the in-progress MINOR.

---

## 6. "Plays well together" verification protocol

For each ship cycle, the orchestrator MUST:

1. **Verify shared tree state BEFORE cherry-pick.** `git -C <worktree> rev-parse HEAD` must equal the published integration tip.
2. **Run smoke tests after cherry-pick:** `cargo test --all`, `pytest -x -m "not slow"`, smoke build of `_rust.so`.
3. **Verify CHANGELOG + version bump sequence.** New entry at top; `__version__` matches tag; `pyproject.toml` matches.
4. **After ship: resync shared tree** (`git reset --hard HEAD` after every `update-ref`) so all worktrees see the new tip. Per no-concurrent-branch-ops rule.
5. **Persona acceptance re-run after every MINOR** (v1.4.0, v1.5.0): Phases 1 + 1E + 2 + 3. PATCH releases skip the full re-run unless the patch touches a persona-tested surface.

---

## 7. Honest risks

- **PR 15 + PR 17 both land cleanly:** the second is a redundant superset. Pick one; document the choice. Default: Plan C wins (true Nash). Flips only if Option A delivers materially better perf AND Plan C's Nash convergence is unproven — decision must be explicit with measured numbers.
- **PR 21 exposes regret-update bugs:** Type B. Fix in place, ship as v1.4.1. Do not block v1.4.0 on speculative regression concerns.
- **PR 22 hits a PyInstaller bundling issue with new Rust code:** Type B. Ship as `v1.x.y+1`. Universal2 was the canary on this surface (v1.2.1); the framework is exercised.
- **Persona Phase 2 reveals Plan C's "true Nash" is only approximate at production scale:** Type C-CRITICAL; blocks ship. Triage with user before tagging.
- **PR 19 + PR 20 bundle hits conflicting CHANGELOG entries:** low risk; hand-merge in the bundled cherry-pick.

---

## 8. "Plays well" verdict

**Are the five in-flight tracks compatible? YES, with one caveat.**

- PR 19 + PR 20 are fully orthogonal to everything else; ship as bundled v1.3.1 with zero risk.
- **PR 15 and PR 17 are mutually exclusive in practice** — Plan C is a strict semantic superset of Option A. If both audit-clear, ship Plan C only.
- PR 21 is orthogonal to PR 19/20 and semantically orthogonal to PR 15/17. Textual conflicts on `solver.py` are tractable (5-30 lines).

**No blocking conflict is predictable BEFORE landing.** Single conscious coordination decision: **if Option A and Plan C both pass audit, only Plan C ships.** Everything else is mechanical sequencing.
