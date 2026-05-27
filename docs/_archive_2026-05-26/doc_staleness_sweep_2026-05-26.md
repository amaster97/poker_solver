# Doc Staleness Sweep — Second-Pass on Tracked Main-Line Docs (2026-05-26)

**Auditor:** doc-staleness sweep agent (read-only, ~30 min budget)
**Mode:** READ-ONLY scan + fix-list; no edits.
**Scope:** tracked-on-`origin/main` docs (README, USAGE, CHANGELOG, CONTRIBUTING, DEVELOPER, PLAN, and docs/*.md NOT dated 2026-05-26 that are reachable from main-line). Earlier triage archived obvious stale dated drafts; this pass catches drift in the docs end users actually read.

---

## TL;DR

**Three categories of stale claims are concentrated in README / USAGE / CHANGELOG / DEVELOPER and warrant a follow-up doc-fix PR (HIGH-priority):**

1. **"v1.7.2 fixes the .dmg fork-bomb" (8 hits across README + USAGE + CHANGELOG + dmg_spawn_loop_rca).** v1.7.1 has been closed as obsolete per `docs/v1_7_1_tag_decision_2026-05-26.md`; the .dmg fork-bomb fix is folding into v1.8.0 per `docs/v1_8_0_release_notes_DRAFT.md`. README/USAGE/CHANGELOG still tell the user the fix ships in v1.7.2.
2. **"A83 33-pp deep-cap divergence under investigation / v1.6.1 HELD" (~6 hits in README + CHANGELOG + 1 in aggregator_vs_true_nash_explainer.md).** Investigation closed per `a83_deep_cap_root_cause_investigation.md` + `matched_config_investigation.md` + `terminal_utility_audit_2026-05-26.md`: math is established, divergence is Nash-multiplicity (both solvers within indifference manifold; Brown exploitability 0.06 chips at 2000 iters = 0.006% of pot), NOT a bug. The v1.6.1 hold has been LIFTED per `docs/v1_6_1_ship_hold_review_2026-05-26.md`; bundle has shipped piecewise on `origin/main`.
3. **"Expected 4-8× SIMD speedup" claim in CHANGELOG v1.5.0 entry** still asserts the projected number; bench (`v1_8_simd_perf_benchmark_2026-05-26.md`) measured ~1.0× on this hardware. The release-notes draft already retracts the claim; CHANGELOG line 189 still carries it.

**One MEDIUM-priority broken-link cluster:** 3 stale CHANGELOG cross-links to docs that don't exist (`docs/architecture.md`, `docs/pushfold_v1_generation_notes.md`, `docs/release_notes_v0.3.md`) plus 2 broken `docs/pr4_5_audit_debt/*.md` links.

**Recommendation:** open a follow-up doc-fix PR for category 1 + 2 (HIGH); batch the CHANGELOG SIMD claim + broken links + lower-priority fixes into a separate medium-PR.

---

## Methodology

1. Read `README.md`, `USAGE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `DEVELOPER.md` end-to-end.
2. Sampled `PLAN.md` via grep for stale version / HELD / A83 / 33-pp patterns (full read would burn budget).
3. Sampled `docs/*.md` not dated 2026-05-26 via grep for the same patterns; spot-checked `aggregator_vs_true_nash_explainer.md`, `dmg_install_guide.md`, `dmg_spawn_loop_rca_2026-05-26.md` end-to-end.
4. Verified 2026-05-26-dated docs only if they contain TBD / queued / pending claims (looked at v1.8.0 release-notes DRAFT, v1.7.1 tag decision, v1.6.1 ship-hold review, v1.8 SIMD perf benchmark).
5. Built link inventory from main-line docs and verified each target exists.
6. Cross-referenced PR claims against `gh pr list --state merged`.

**State-of-truth anchors as of 2026-05-26 02:20 (file mtimes):**

- `pyproject.toml`: `version = "1.7.0"`
- All PRs #5/#8/#9/#10/#12/#14/#15/#18 = v1.7.1 bundle slots 1–9: **MERGED on origin/main**.
- PR #22 = supersedes PR #19 (v1.7.1 slot 10 = PR 60 Brown hard-fail): MERGED.
- PR #21 = v1.7.2 CI release workflow: MERGED.
- PR #23, #33, #35, #41, #32 = v1.8 Phases 1-4 + AVX2: MERGED.
- PR #42 = .dmg fork-bomb fix (freeze_support): MERGED commit `728206e`.
- No `v1.7.1` / `v1.7.2` / `v1.8.0` tags exist; next clean release boundary is **v1.8.0**.
- v1.6.1 hold: **LIFTED** per `docs/v1_6_1_ship_hold_review_2026-05-26.md`.

---

## HIGH-priority stale claims

### H1. README — "fix queued for v1.7.2"

**File:line:** `README.md:25, 28, 33, 228`

**Stale text (representative):**

```
> ⚠️ **CRITICAL:** the v1.6.0 `.dmg` currently spawns processes
> uncontrollably on Finder launch and can freeze your Mac. Root cause
> identified (missing `multiprocessing.freeze_support()` in the
> PyInstaller entry point); fix queued for v1.7.2. Until then, use the
> source install below.
```

```
### macOS install (.dmg — NOT RECOMMENDED until v1.7.2)
```

```
  The fix is patched on `pr-78-dmg-freeze-support-fix` (this PR);
  re-packaged `.dmg` will ship in v1.7.2. **Use the source install
  above** until then.
```

**Recommended replacement:**

The fork-bomb fix already MERGED via PR #42 (commit `728206e`). The repackaged build is shipping in v1.8.0 (next tag), not v1.7.2. Replace "v1.7.2" with "v1.8.0" and reframe from "queued" to "merged on `main`; awaiting tag+release":

```
> ⚠️ **CRITICAL:** the v1.6.0 `.dmg` currently spawns processes
> uncontrollably on Finder launch and can freeze your Mac. Root cause
> identified (missing `multiprocessing.freeze_support()` in the
> PyInstaller entry point); fix merged on `main` (PR #42, commit
> `728206e`) and ships in v1.8.0. Until v1.8.0 is tagged + released,
> use the source install below.
```

```
### macOS install (.dmg — NOT RECOMMENDED until v1.8.0)
```

```
  re-packaged `.dmg` ships in v1.8.0. **Use the source install
  above** until then.
```

**Priority:** **HIGH** — user-facing landing-page text. A user reading the README today is told to wait for a release that won't happen.

---

### H2. USAGE — "fix queued for v1.7.2"

**File:line:** `USAGE.md:46, 51`

**Stale text:**

```
> point; fix queued for v1.7.2. Until then, use **Path B** below.
```

```
remains in the repo; once the packaging fix lands and a re-signed v1.7.2
build is verified, this section will be restored with a working install
flow.
```

**Recommended replacement:** same v1.7.2 → v1.8.0 substitution as H1; also reframe "fix queued" → "fix merged on `main`, shipping in v1.8.0".

**Priority:** **HIGH** — user-facing.

---

### H3. CHANGELOG — entire `## [1.7.2] - 2026-05-26` entry

**File:line:** `CHANGELOG.md:16-34`

**Stale text:** the `## [1.7.2] - 2026-05-26` section asserts v1.7.2 is a tagged release that ships the freeze_support fix. Per `docs/v1_7_1_tag_decision_2026-05-26.md`, **neither v1.7.1 nor v1.7.2 will be tagged**; v1.7.1 is closed as obsolete and v1.7.2's CI workflow / Guards landed but the freeze_support fix folds into v1.8.0.

**Recommended replacement:** either rename the `## [1.7.2]` section to `## [1.8.0]` and roll the entry forward, OR strike the `## [1.7.2]` section entirely and add the freeze_support fix to a forthcoming `## [1.8.0]` section. The v1.7.2 entry as currently written claims a release that doesn't exist.

**Also stale:** `CHANGELOG.md:28, 33, 61-64` — "Use the v1.7.2 repackaged build instead" / "ships in v1.7.2" — fix to v1.8.0.

**Priority:** **HIGH** — CHANGELOG is the authoritative release log; an entry for a non-existent release is a structural bug. (Note: end users are unlikely to look here before the README, but the inconsistency is visible to any auditor / contributor.)

---

### H4. README — "v1.5.0 Brown acceptance test currently FAILS — v1.6.1 ship HELD"

**File:line:** `README.md:234-252` (entire bullet under Known issues)

**Stale text (key fragments):**

```
- **v1.5.0 Brown acceptance test currently FAILS — v1.6.1 ship HELD
  pending investigation.** ... empirically re-confirms a residual algorithmic
  divergence at deep-cap facing-raise** (not yet localized): on A83 at
  `b1000r3000`, bottom-pair-Ace cells (3sAs, 3cAc) show 33-pp call-frequency
  divergence (Brown ~0.36, Rust ~0.69), max |diff| 0.33. ...
  Investigation in flight: best-response cross-check + iteration sweep
  + facing-raise path re-read.
```

**Recommended replacement:** Investigation has concluded. Per `docs/a83_deep_cap_root_cause_investigation.md` + `docs/matched_config_investigation.md` + `docs/terminal_utility_audit_2026-05-26.md`:

- Math is established: DCFR weighting audit + 3 independent code reviews + terminal-utility audits all PASS.
- Matched-config investigation (2026-05-25 VERDICT C) confirmed: forcing identical action menus produces bit-identical strict-gate numbers.
- The deep-cap divergence is **Nash-multiplicity at depth ≥ 11 facing-all-in `(c, f)` AA leaves**. Brown exploitability 0.06 chips at 2000 iters = 0.006% of pot — both solvers are essentially Nash, landed on different points within the same indifference manifold.
- v1.6.1 hold has been **LIFTED** per `docs/v1_6_1_ship_hold_review_2026-05-26.md`; the engine bundle (PR 50, 51, 52, 54, 55, 56, 53b, 53c) has shipped piecewise on `origin/main`.

Suggested replacement bullet (compressed):

```
- **Deep-cap RvR acceptance vs Brown: Nash-multiplicity on indifference
  manifold (resolved).** Earlier 33-pp K72/A83 deep-cap divergence
  traced to two compound causes, both resolved: (1) test-side wrapper
  bugs (suit-encoding, P0/P1 player convention, hand-string sort
  order) — fixed in the v1.7.1 bundle (PR 52/55/56); (2) Nash-
  multiplicity at depth ≥ 11 facing-all-in `(c,f)` AA leaves — both
  solvers within the indifference manifold (Brown exploitability
  0.06 chips at 2000 iters = 0.006% of pot). Acceptance test reframed
  to a 4-layer gate (structural + shallow-strict + deep max-L1 ≤ 1.9
  + top-action ≥ 60%); PR 53b/53c passing on `main`. Investigation
  details: `docs/a83_deep_cap_root_cause_investigation.md`,
  `docs/matched_config_investigation.md`,
  `docs/terminal_utility_audit_2026-05-26.md`.
```

**Priority:** **HIGH** — top of Known issues; this is the second item a user sees there. The current text overstates the engine's problems by ~6 months of accumulated investigation.

---

### H5. README Status block — "v1.6.1 ... is held pending the A83 acceptance test resolution"

**File:line:** `README.md:15-18`

**Stale text:**

```
- **Latest tagged release:** v1.7.0 (aggregator→vector wiring + CLI
  subcommands — PR 43 + PR 44). The v1.0 → v1.7.0 trajectory is
  documented in [`CHANGELOG.md`](CHANGELOG.md). v1.6.1 (engine bundle,
  deep-cap investigation) is held pending the A83 acceptance test
  resolution.
```

**Recommended replacement:** A83 is resolved. v1.6.1 hold has been lifted. The engine bundle is on `main`; the next tag will be v1.8.0 which folds in the v1.6.1 engine bundle + v1.7.2 CI hardening + .dmg fork-bomb fix + v1.8 SIMD. Suggested:

```
- **Latest tagged release:** v1.7.0 (aggregator→vector wiring + CLI
  subcommands — PR 43 + PR 44). The v1.0 → v1.7.0 trajectory is
  documented in [`CHANGELOG.md`](CHANGELOG.md). **Next release:
  v1.8.0** (cross-platform SIMD + .dmg fork-bomb fix + v1.6.1 engine
  bundle + v1.7.2 CI hardening, all merged on `main`; tag pending).
```

**Priority:** **HIGH** — top-of-README Status block; first thing a user sees.

---

### H6. CHANGELOG — v1.7.0 Status sub-section says "v1.6.1 engine bundle: HELD"

**File:line:** `CHANGELOG.md:49-54`

**Stale text:**

```
### Status

- v1.6.1 engine bundle: HELD pending acceptance gate redefinition
  (deep-cap Brown apples-to-apples reveals architectural divergence
  in payoff convention; see internal mirror v1.6.1 no-go synthesis)
- PR 44 .dmg packaging fix: VERIFIED on disk; ready for Gate 5 attachment
```

**Recommended replacement:** Hold lifted per `docs/v1_6_1_ship_hold_review_2026-05-26.md`. Update to:

```
### Status

- v1.6.1 engine bundle: shipped piecewise on `main` (PR 50, 51, 52,
  54, 55, 56, 53b, 53c); folded into v1.8.0.
- PR 44 .dmg packaging fix: VERIFIED on disk; superseded by PR #42
  freeze_support fork-bomb fix (commit `728206e`).
```

**Priority:** **HIGH** — CHANGELOG visible.

---

### H7. CHANGELOG v1.6.0 Notes — "deferred to v1.6.1 pending per-action divergence diagnosis"

**File:line:** `CHANGELOG.md:75-78`

**Stale text:**

```
### Notes
- Engine bundle (PR 33+34+35 for true Brown parity) still deferred to v1.6.1 pending per-action divergence diagnosis
- GUI is functionally complete for Gate 2; awaiting engine acceptance test PASS before final persona retest sweep
- Per `feedback_ui_packaging_sync`: this ship triggers PR 11 .dmg rebuild (LEG 19 candidate) + PR 10b UI re-audit downstream
```

**Recommended replacement:** Mark Notes block as historical (e.g., add a retroactive amendment marker like the v1.6.0 .dmg fork-bomb retroactive amendment at line 58-64) and roll forward; the engine bundle has shipped on `main` and Gate 2 is closed.

**Priority:** **HIGH** — same misleading-state-of-engine signal as H6.

---

### H8. CHANGELOG v1.5.0 SIMD deferred — "expected 4-8x speedup"

**File:line:** `CHANGELOG.md:189-190`

**Stale text:**

```
- SIMD kernels for vector-shape arithmetic (expected 4-8x speedup based
  on PR 8 NEON-on-scalar experience).
```

**Recommended replacement:** The empirical bench (`docs/v1_8_simd_perf_benchmark_2026-05-26.md`) measured ~1.0× on M4 Pro arm64 for the vector-form CFR workloads the SIMD code touches; the v1.8.0 release-notes draft already flagged this. Update the v1.5.0 Deferred-to-v1.5.1+ block to:

```
- SIMD kernels for vector-shape arithmetic (subsequently wired in v1.8;
  empirical bench measured ~1.0× on the vector-form CFR workload —
  bottleneck is per-iter scalar work outside the SIMD inner loops).
```

(The v1.5.0 entry is historical; the right framing is "we shipped it; it didn't deliver the projected speedup.")

**Priority:** **HIGH** — false performance claim. A reader extrapolating from this line will mis-estimate the engine's perf envelope.

---

## MEDIUM-priority stale claims

### M1. README — Quick start "~24x faster" claim

**File:line:** `README.md:93`

**Stale text:**

```
# Same river subgame on the Rust tier (~24x faster):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust
```

**Status:** This number originates from `DEVELOPER.md:25` (3.88 s Rust vs 92.9 s Python at 100k iters on M4 Pro) which is anchored at v1.4.x. Probably still roughly accurate, but unverified post-v1.8 SIMD wiring. Low risk.

**Priority:** **MEDIUM** — confirm bench is still ~24× on `main`, else update or hedge ("measured ~24× on v1.4.x; v1.8 SIMD did not shift this ratio per `docs/v1_8_simd_perf_benchmark_2026-05-26.md`").

---

### M2. README UI section — ".dmg GUI does not currently work"

**File:line:** `README.md:184-185`

**Stale text:**

```
v1.2.0 the UI drives the real solver. The packaged `.dmg` GUI does not
currently work — see Known issues. **Use the CLI / Python API for now.**
```

**Status:** Technically still accurate (.dmg is held for fork-bomb fix), but the cross-reference to "Known issues" only makes sense once H1/H5 above are also fixed. The "does not currently work" framing is also weaker than the actual fork-bomb hazard — a fresh user might double-click anyway and lose their session.

**Priority:** **MEDIUM** — re-anchor in the H1 fork-bomb framing for consistency.

---

### M3. USAGE — "ad-hoc signed (not notarized)" + "universal2" reference

**File:line:** `USAGE.md:54-57`

**Stale text:**

```
arm64-only. The "universal2" claim that appeared in earlier release labeling
was retired in PR 44 (DMG filename now matches the actual arch) and
reinforced in PR 86 (build script enforces `lipo -info architecture: arm64`
post-build).
```

**Status:** PR 86 doesn't exist in `gh pr list --state merged`; the lipo enforcement seems to have shipped via PR #47 ("fix(dmg): arch label + version stamp accuracy", merged 2026-05-26 06:27). Reference is to an internal PR number that didn't map to an upstream merge.

**Priority:** **MEDIUM** — internal-PR-number drift; refactor to a SHA-anchored reference or PR #47.

---

### M4. README v1.5.0 Brown text — duplicates Known-issues claim

**File:line:** `README.md:165-170`

**Stale text:**

```
- **`solve_range_vs_range_rust`** (vector form, v1.5.0;
  `crates/cfr_core/src/dcfr_vector.rs` via PyO3) — joint range Nash via
  Brown's vector-form CFR. Structurally a port of `noambrown/poker_solver`'s
  `cpp/src/trainer.cpp:138-240` per three independent code reviews,
  but empirical acceptance against Brown's binary still diverges on
  deep-cap facing-raise spots (33-pp on bottom-pair-Ace cells in the
  A83 spot at `b1000r3000`); shallow-cap behavior matches — see Known
  issues.
```

**Status:** Same H4 issue, restated mid-paragraph in the Python API description block. The "still diverges" claim is now refuted by Nash-multiplicity resolution.

**Recommended replacement:** roll into the H4 fix; this paragraph should reference the resolved A83 framing, not the open one.

**Priority:** **MEDIUM** — duplicate of H4 but in a different section of README.

---

### M5. Aggregator-vs-true-Nash explainer — "investigation in flight"

**File:line:** `docs/aggregator_vs_true_nash_explainer.md:22-23, 123-138`

**Stale text:**

```
empirical parity verified on shallow-cap spots, currently under investigation for a
deep-cap facing-raise divergence — see Example 3).
```

```
**However, a v1.6.1-bundle dry-run (PR 33+34+35-A+B+40 composed)
empirically re-confirms a residual algorithmic divergence at deep-cap
facing-raise that the structural reviews did not surface.** On A83 at
`b1000r3000`, bottom-pair-Ace cells (3sAs, 3cAc) call ~0.69 in Rust
vs ~0.36 in Brown — 33-pp delta, max |diff| 0.33. ...
Investigation in flight: best-response cross-check, iteration sweep
500/1000/2000/4000/8000, and side-by-side re-read of
`dcfr_vector.rs::traverse` vs `trainer.cpp:138-240` on the
facing-raise path. Full report: `docs/v1_6_1_dryrun_verification.md`.
```

**Status:** Aggregator-vs-true-Nash explainer is linked from BOTH README and USAGE (`docs/aggregator_vs_true_nash_explainer.md`); this is user-reachable. Investigation is closed (see H4).

**Recommended replacement:** mirror H4 (Nash-multiplicity resolution + reframed gate); strike the "in flight" wording.

**Priority:** **MEDIUM** — reachable via README/USAGE link.

---

### M6. dmg_spawn_loop_rca — "Use v1.7.1 or later" / "Upgrade to v1.7.1"

**File:line:** `docs/dmg_spawn_loop_rca_2026-05-26.md:197, 199, 210, 290`

**Stale text:**

```
**Status:** Do NOT use v1.6.0. Use v1.7.1 or later.
```

```
**Fix:** Upgrade to v1.7.1 or later. The .dmg has been corrected in subsequent releases.
```

```
| v1.7.1 | GUI re-introduced (v1.6 engine) | Likely still vulnerable |
```

**Status:** v1.7.1 isn't going to be tagged (closed as obsolete). The freeze_support fix ships in v1.8.0. This doc is reachable via the prominent README warning and the USAGE Path A warning.

**Recommended replacement:** "Use v1.8.0 or later" globally; remove the v1.7.1 row from the per-release vulnerability table or mark as "skipped — folded into v1.8.0".

**Priority:** **MEDIUM** — directly user-reachable via README + USAGE; the README/USAGE messages route the user here for the RCA. Once they read this doc, they're told to install a release that won't ship.

---

### M7. CHANGELOG broken cross-links

**File:line:** `CHANGELOG.md` references to non-existent docs

**Broken targets:**

- `docs/architecture.md` (referenced from CHANGELOG; does not exist)
- `docs/pushfold_v1_generation_notes.md` (referenced from CHANGELOG; does not exist)
- `docs/release_notes_v0.3.md` (referenced from CHANGELOG; does not exist)
- `docs/pr4_5_audit_debt/audit_report.md` (referenced from CHANGELOG; does not exist)
- `docs/pr4_5_audit_debt/launch_kickoff.md` (referenced from CHANGELOG; does not exist)

**Verified working:** `docs/pr_proposals/v1_4_asymmetric_contributions.md`, `docs/pr_proposals/v1_4_node_locking.md`, `docs/pr8b_prep/feasibility_study.md`, `docs/pr8b_prep/scope.md`, `docs/aggregator_vs_true_nash_explainer.md`, `docs/dmg_install_guide.md`, `docs/dmg_spawn_loop_rca_2026-05-26.md`, `docs/river_parity_timeout_investigation_2026-05-23.md`.

**Recommended action:** either restore the missing docs (likely lost during the 2026-05-23 doc archive sweep) or remove the dead references from CHANGELOG. The `architecture.md` reference is likely meant to point at `DEVELOPER.md`.

**Priority:** **MEDIUM** — broken navigation for anyone reading the CHANGELOG; not user-blocking but degrades signal.

---

## LOW-priority observations

### L1. USAGE document baseline header

**File:line:** `USAGE.md:1-12`

```
# Using poker_solver — End-User Guide (v1.7.x)
...
Document baseline: v1.0.0. Updates through v1.7.0 are layered in §5.3
```

Already correct for v1.7.0; will need a refresh once v1.8.0 ships (forward-looking note, not stale today).

**Priority:** **LOW** — defer until v1.8.0 tag.

---

### L2. dmg_install_guide.md — anchored on v1.6.0

**File:line:** `docs/dmg_install_guide.md:1-19`

The entire guide is structured around `Poker-Solver-1.6.0-arm64.dmg` (45 MB, SHA256 `0443e8f0...`). After H1/H5 land, this guide will need a forward port to v1.8.0 once the new SHA / size are known. The doc already carries a top-of-file warning (line 2-7).

**Priority:** **LOW** — defer until v1.8.0 .dmg is built and ready to publish.

---

### L3. PLAN.md sprawl

`PLAN.md` is 102 KB and a moving target by design. The grep sweep found dozens of "v1.7.1 in flight" / "HELD" / "33-pp" claims that are stale in the same way as README/USAGE/CHANGELOG. Per the `feedback_continuous_pruning` rule, PLAN.md prune is a separate workstream. Not gating user experience; surfacing here only as a marker.

**Priority:** **LOW** — handle via continuous-pruning workstream, not the doc-fix PR.

---

### L4. README "v1.5.0 Brown ... shallow-cap behavior matches" (line 168-169)

Statement is accurate per matched-config investigation; "see Known issues" cross-reference is the only thing that becomes stale after H4 lands.

**Priority:** **LOW** — fold into H4 fix.

---

### L5. USAGE §6 What's coming "PR 9 ... v1.1.0 / PR 10b ... PR 8"

**File:line:** `USAGE.md:755-769`

```
- **PR 9 — full HUNL preflop solve.** Replaces the `NotImplementedError`
  above 15 BB. Shipping in v1.1.0.
- **PR 10b — real solver bindings in the UI.** ...
- **PR 8 — NEON SIMD and public chance sampling.** Rust tier perf work;
  brings standard-flop solve time well below the 10-hour projection.
```

These PR references are v1.0.0-era; v1.0.0 baseline is explicitly documented (line 32, 35). Updating would require knowing the current roadmap state; deferring.

**Priority:** **LOW** — strict-historical context.

---

## Cross-reference link audit

### Links from main-line docs — all verified

From `README.md`:
- `[CHANGELOG.md](CHANGELOG.md)` — exists.
- `[`docs/dmg_spawn_loop_rca_2026-05-26.md`]` — exists.
- `[`docs/dmg_install_guide.md`]` — exists.
- `[`docs/aggregator_vs_true_nash_explainer.md`]` — exists.
- `[`USAGE.md`]` — exists.
- `[`DEVELOPER.md`]` — exists.
- `[`CONTRIBUTING.md`]` — exists.
- `[LICENSE](LICENSE)` — not verified (out of scope; non-md).

From `USAGE.md`:
- `[`docs/dmg_spawn_loop_rca_2026-05-26.md`]` — exists.
- `[`docs/dmg_install_guide.md`]` — exists.
- `[`CHANGELOG.md`](CHANGELOG.md)` — exists.

From `CHANGELOG.md`:
- `docs/architecture.md` — **BROKEN** (M7).
- `docs/pr4_5_audit_debt/audit_report.md` — **BROKEN** (M7).
- `docs/pr4_5_audit_debt/launch_kickoff.md` — **BROKEN** (M7).
- `docs/pr8b_prep/feasibility_study.md` — exists.
- `docs/pr8b_prep/scope.md` — exists.
- `docs/pr_proposals/v1_4_asymmetric_contributions.md` — exists.
- `docs/pr_proposals/v1_4_node_locking.md` — exists.
- `docs/pushfold_v1_generation_notes.md` — **BROKEN** (M7).
- `docs/release_notes_v0.3.md` — **BROKEN** (M7).
- `docs/river_parity_timeout_investigation_2026-05-23.md` — exists.
- `docs/dmg_spawn_loop_rca_2026-05-26.md` — exists.

From `DEVELOPER.md`:
- `[`README.md`](README.md)` — exists.
- `[`CONTRIBUTING.md`](CONTRIBUTING.md)` — exists.
- All `tests/test_*.py` and `poker_solver/*.py` links — out of scope (code paths).

From `CONTRIBUTING.md`:
- `[README.md](README.md)` — exists.
- `[CHANGELOG.md](CHANGELOG.md)` — exists.

**Net: 5 broken cross-links, all from CHANGELOG.**

---

## Suggested follow-up PR plan

### PR A (HIGH-priority doc-fix; recommend kicking off now)

**Title (suggested):** `docs: rectify stale .dmg / v1.7.x / A83 / SIMD claims post-2026-05-26 session`

**Scope:** H1 through H8 — 8 distinct fix-spots concentrated in `README.md`, `USAGE.md`, `CHANGELOG.md`. Single-PR, all docs-only, no code or test changes. Estimated diff size: ~80-150 lines added/changed across the three files.

**Test plan:** zero engine impact; `markdownlint` if configured; manual eyeball review against the H4/H6 framing anchors (`docs/v1_6_1_ship_hold_review_2026-05-26.md`, `docs/v1_7_1_tag_decision_2026-05-26.md`, `docs/v1_8_0_release_notes_DRAFT.md`, `docs/v1_8_simd_perf_benchmark_2026-05-26.md`).

**Audit-class:** **Type A docs-only** per `feedback_persona_test_rectification.md`; clears for autonomous commit if audit-clean.

### PR B (MEDIUM-priority; batch later)

**Scope:** M1 through M7. Includes `docs/aggregator_vs_true_nash_explainer.md` Nash-multiplicity reframe (M5), the `docs/dmg_spawn_loop_rca_2026-05-26.md` v1.7.1→v1.8.0 substitution (M6), and the CHANGELOG broken-link restoration (M7). The "~24x faster" bench reverification (M1) requires a perf run, not just a doc edit; defer the verification step if running it now is out of budget.

**Test plan:** as PR A + bench rerun for M1.

### LOW-priority items

L1-L5: defer until v1.8.0 tag or fold into PLAN-prune workstream.

---

## Open questions surfaced by this sweep

1. **Is v1.7.2 the version label for the .dmg fork-bomb fix, or v1.8.0?** Per `docs/v1_7_1_tag_decision_2026-05-26.md` and `docs/v1_8_0_release_notes_DRAFT.md`, v1.7.1 closes-as-obsolete and v1.8.0 is the next clean release boundary. The CHANGELOG `## [1.7.2] - 2026-05-26` entry contradicts this; the README/USAGE "queued for v1.7.2" claims also contradict it. **Decision needed before PR A:** pick a single version label and apply consistently.
2. **Should the CHANGELOG v1.6.0 Notes block carry a 2026-05-26 retroactive amendment block (like the .dmg fork-bomb one at line 58-64) for the engine-bundle-shipped status?** Recommendation: yes, mirror the pattern.
3. **Are the 5 broken CHANGELOG cross-links (M7) genuinely orphaned, or were they archived during the 34-doc archive sweep (PR #52)?** Spot-check the archive directory before assuming the docs are gone.
