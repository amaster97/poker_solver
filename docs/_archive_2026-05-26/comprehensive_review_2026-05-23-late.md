# Comprehensive Consistency Review — 2026-05-23 (LATE / end-of-day)

**Companion to:** `comprehensive_review_2026-05-23.md` (kept as historical snapshot).
**Reason for re-issue:** original was filed between v1.3.0 ship + LEG 5 staging; v1.3.1, v1.3.2, and v1.4.0 all shipped after. Wake-up brief flagged it as "understated by one PATCH + one MINOR." This refresh captures end-of-day truth.

---

## Section 1 — State snapshot (actual end-of-day)

### Versions shipped today (origin/main + `git tag`)

| Tag | Commit | What |
|---|---|---|
| v1.0.1 | `e9156a8` | PR 8 NEON SIMD + cache layout + PCS infra (PATCH; 10x gate NOT MET; PR 8b parked) |
| v1.1.0 | `ddbd7a1` | PR 9 HUNL preflop subgame solver + equity-leaf substitution |
| v1.2.0 | `1ddb75b` | PR 10b real-solver UI bindings |
| v1.2.1 | `1c92032` | universal2 `_rust.so` patch (PR 14, W1.4 arch fix) |
| v1.3.0 | `ee709b2` | PR 16 Pluribus-blueprint range-vs-range aggregator (Option B) |
| v1.3.1 | `6152cab` | PR 20 `hero_player` gap fix + honest USAGE caveats (PATCH) |
| v1.3.2 | `9021c5e` | PR 15 Rust port of exploitability + game-value walks (W1.5 perf fix) |
| v1.4.0 | `30ce9e2` | PR 21 node locking (Python + Rust); Daniel persona W3.1/3.2/3.3 unblocked |

**Origin/main tip:** `166d2b8` — the v1.4.0 release commit; CHANGELOG, `pyproject`, and `__version__` are all coherent at `1.4.0`.

**Today's release count:** **9 versions** (v1.0.0 → v1.0.1 → v1.1.0 → v1.2.0 → v1.2.1 → v1.3.0 → v1.3.1 → v1.3.2 → v1.4.0). The early review only knew about the first 6; v1.3.1, v1.3.2, and v1.4.0 are the post-publish deltas.

### In flight (NOT shipped at session close)

- **PR 22 — Asymmetric initial-contributions (`pr-22-asymmetric-contributions` branch).** Design doc at `docs/pr_proposals/v1_4_asymmetric_contributions.md`. Unblocks Daniel W3.4 + Sarah W2.3 + Marcus W1.2. Implementer-not-yet-spawned per the LEG 9 plan; worktree exists. ETA 2.5–3.5 days; v1.4.1 target.
- **LEG 10** — would bundle PR 22 + v1.4.1 follow-ups. No runbook on disk yet.

### Deferred

- PR 8b (`FlatInfosetStore` primary-wire); PR 12 (3-handed); Plan C (parked at `ea2511c`, superseded by PR 15); Stage C1 (killed). W-DL-05 GUI visualizer. v1.5/v2 backlog: Q3 exploitability slider, range-based dealing in UI, Rust-side callbacks, full-tree preflop.

---

## Section 2 — Per-PR status (PR 8 → PR 22)

| PR | Status / Tag | Notes |
|---|---|---|
| PR 8 | SHIPPED v1.0.1 | NEON SIMD + cache layout + PCS. 10x gate NOT MET; PR 8b parked. |
| PR 8b | DEFERRED | Feasibility ceiling 3–5x; revisit trigger not met. |
| PR 9 | SHIPPED v1.1.0 | Preflop subgame solver Python + Rust; ~21x Rust speedup. |
| PR 10b | SHIPPED v1.2.0 | UI mock→real swap; `Spot.to_hunl_config()` bug fixed. |
| PR 11 | SHIPPED v1.0.0 | Library + macOS .dmg (v1 GA). |
| PR 14 | SHIPPED v1.2.1 | universal2 `_rust.so`; W1.4 arch BUG closed. |
| PR 15 | SHIPPED v1.3.2 | Rust port of exploitability walk; W1.5 → 26s; closes Type C-CRITICAL. |
| PR 16 | SHIPPED v1.3.0 | Pluribus-blueprint RvR aggregator (Option B). Workaround, not Nash. |
| PR 17 | PARKED | Plan C Rust true-Nash; superseded by PR 15. |
| PR 18 | KILLED | Stage C1 numpy slab; PR 15 obviated speedup target. |
| PR 19 | SHIPPED v1.3.1 | v0.6.2 small-fixes items 2+3 (bundled). |
| PR 20 | SHIPPED v1.3.1 | `range_aggregator` `hero_player` gap + S1/S4 caveats. |
| PR 21 | SHIPPED v1.4.0 | Node locking. 597 LOC + 19 tests. <2% Rust-tier overhead. |
| PR 22 | IN FLIGHT | Asymmetric initial-contributions; spec only; v1.4.1 target. |

Across the day, 9 implementer PRs landed; 1 (PR 22) is the active backlog item.

---

## Section 3 — Persona test loop status

### Closed by code today (retest pending for some)

- **W1.4** (Marcus 100 BB arch ImportError) — universal2 `_rust.so` at v1.2.1. Verified.
- **W1.5** (turn subgame RvR expl walk, was Type C-CRITICAL timeout @ 15 min) — PR 15 / v1.3.2 dropped to 26.43s.
- **W3.1 / W-DL-01** (villain-never-bluffs lock) — PR 21 / v1.4.0. Code-path verified by `tests/test_node_locking.py::test_best_response_heuristic_daniel_workflow`.
- **W3.2 / W-DL-02** (GTO-vs-actual leaky 60% preflop call) — PR 21 / v1.4.0.
- **W3.3 / W-DL-03** (merged range / donk-leads small only with draws) — PR 21 / v1.4.0.

### In flight

- **Phase 2b RvR persona retest.** Re-runs 5 previously-blocked Phase 1E workflows against v1.3.1's `hero_player=1` API. Includes W2.3 + W2.6.

### Future / structurally blocked

- **W3.4** (Daniel MDF half-pot defending) — needs PR 22. Queued for v1.4.1.
- **W-DL-04** (hero's preferred line) — claimed unblocked via inverse node-lock; retest pending.
- **W-DL-05** (multi-street tree visualizer) — GUI-only, Phase 3 polish, v1.4.1+.

**Summary:** 4 loops formally closed today + 1 in flight + 1 PR-22-blocked + 1 GUI-deferred. (Counting W3.1/3.2/3.3 individually gives 5 closed; counting the Phase 1 BUG cohort as one gives 4.)

---

## Section 4 — Drift findings (residual staleness across docs)

Items flagged in the early review still unaddressed, plus new gaps from post-v1.3.0 ships:

1. **PLAN.md** — already worst-offender per early review; v1.4.0 adds another layer. Status / branch / roadmap still describe a pre-PR-15 / pre-PR-21 world. Full rewrite needed.
2. **README.md** — version sticker referenced v1.0.0 in early review; main is now v1.4.0. "What's coming next" still names shipped PRs.
3. **USAGE.md** — header version sticker; §5.2 was added in v1.3.1; no §6 for node locking. Needs `locked_strategies` kwarg coverage.
4. **DEVELOPER.md** — early review fixed L60; now stale on PR 15 + PR 21.
5. **`v1_3_range_vs_range.md`** — body still recommends Option A despite Status SUPERSEDED header.
6. **`v1_3_validation_gate.md`** — Option A is now SHIPPED (PR 15 / v1.3.2), not deferred; threshold framing needs update.
7. **`v1_3_research_alternatives.md`** — needs appendix that PR 15 / Option A shipped and Plan C is parked.
8. **Memory layer** — `post_v1_ga_status.md` + `post_ga_parallel_launch.md` retirement triggers still met.
9. **`project_solver.md`** — needs another bump to reflect v1.4.0 + persona unblocks.
10. **`MEMORY.md`** L18-19 — same as early review; description references "four post-GA PRs in flight," all shipped.
11. **No `pr22_prep/` directory** — PR 22 only has the proposal doc; PR 21 had 3 prep docs by comparison.
12. **CHANGELOG `[Unreleased]`** — lists v1.5/v2 follow-ups but does not mention PR 22 (v1.4.1 target).

---

## Section 5 — Verdict

**Verdict: SHIPPING-ACCURATE INTERNALLY, EXTERNAL DOCS LAG.**

CHANGELOG, `pyproject.toml`, `__init__.py`, and origin/main are all coherent at v1.4.0; the early-review's "v1.3.0 ship state" cross-doc contradiction is closed. Remaining gap is Tier 1 README/USAGE/DEVELOPER + PLAN.md, which still describe a pre-v1.3.x landscape. Not user-facing-breaking — CLI, library API, and CHANGELOG advertise correctly — but documentation is the loudest stale surface.

**Most consequential delta vs the early review:** the early review treated v1.3.0 as "shipped, possibly being reverted via LEG 5." End-of-day reality: v1.3.0 was kept, three forward releases (v1.3.1, v1.3.2, v1.4.0) layered on top, LEG 5 abandoned. The early review's "user decision needed on what v1.3.0 means" is MOOT. Repo is healthier than the early review's "NEEDS-USER-REVIEW" verdict implied.

**Next session priority:** Tier 1 doc refresh pass. All four are >1 minor version stale.
