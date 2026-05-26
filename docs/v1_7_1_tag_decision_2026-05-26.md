# v1.7.1 Tag Decision — 2026-05-26

**Auditor:** v1.7.1 closure agent (one-shot, ~20 min budget)
**Mode:** read-only audit + decision + report
**Decision:** **CLOSE v1.7.1 as obsolete; bundle is shipped piecewise on `main`. Folding into v1.8.0.**

---

## TL;DR

All 10 PRs from the v1.7.1 bundle are landed on `origin/main` (PR 60 via functional supersession by PR #22). However:

- **No version bump commit was ever pushed** — `pyproject.toml` / `__init__.py` / `Cargo.toml` still read `1.7.0` / `0.7.0`.
- **No `v1.7.1` tag exists**, locally or on origin.
- **No GitHub release exists** for v1.7.1.
- **No clean tag boundary exists on `origin/main`** where all 10 bundle PRs are merged but no v1.7.2/v1.8 work is included — they are temporally interleaved.

The next coherent release boundary is **v1.8.0**, which will already include every v1.7.1 fix as part of its baseline. Tagging "v1.7.1" at any current SHA would mislabel a release that also contains substantial v1.7.2 (CI hardening) and v1.8 (SIMD) work.

---

## Bundle composition (10 PRs)

Per `docs/STATUS_2026-05-24_v1_7_1_ship_ready.md` + `docs/leg22_v1_7_1_ship_report.md` + `scripts/ship_v1_7_1.sh`:

| Slot | PR | Topic | Cherry-pick SHA |
|---|---|---|---|
| 1 | PR 50 | Facing-all-in action menu guard (paired Rust + Python) | `18a7640e` |
| 2 | PR 51 | `dcfr_vector.rs:651` off-by-one on asymmetric ranges | `78c71557` |
| 3 | PR 52 | Suit-encoding char swap in `noambrown_wrapper` | `9e6662b6` |
| 4 | PR 54 | Renderer `stack_ceiling` kwarg | `f389b433` |
| 5 | PR 55 | P0/P1 player-convention swap (output side) | `ac7c6406` |
| 6 | PR 56 | Hand-string sort-order canonicalization | `950b82c0` |
| 7 | PR 53b | Acceptance test 4-layer reframe (rebased on PR 54) | `3e50b760` |
| 8 | PR 53c | Layer 3 max L1 ceiling 1.0 -> 1.9 | `ba1c7162` |
| 9 | PR 59 | `memory_profiler` golden file refresh for PR 50 | (rebased) |
| 10 | PR 60 | Hard-fail Brown acceptance gate on missing prereqs | `bde2e12` |

---

## Land status on `origin/main`

| PR | Bundle slot | Status on `origin/main` | Merged-as SHA (squash) | gh PR # |
|---|---|---|---|---|
| 50 | 1 | LANDED | `6c9d7f0b` | #5 |
| 51 | 2 | LANDED (re-opened as PR #16) | `2d7ea585` | #6 closed → #16 merged |
| 52 | 3 | LANDED | `a2a75bed` | #8 |
| 54 | 4 | LANDED | `9a5c4d44` | #9 |
| 55 | 5 | LANDED | `3af1257a` | #10 |
| 56 | 6 | LANDED | `3899ca60` | #12 |
| 53b | 7 | LANDED | `0aec0a7d` | #14 |
| 53c | 8 | LANDED | `49c14211` | #15 |
| 59 | 9 | LANDED | `1bb699e9` | #18 |
| 60 | 10 | **LANDED VIA SUPERSESSION** (PR #22 Guard C delivers functional equivalent — `_skip_or_fail()` helper + `STRICT_ACCEPTANCE=1` env var) | `1fefaff0` | #19 CLOSED → #22 merged |

**Result: 10/10 effectively on `main`.**

PR #19 (PR 60) was closed without merging on 2026-05-25 with the comment: *"Superseded by PR #22 Guard C (commit 1fefaff) which added equivalent _skip_or_fail() helper using STRICT_ACCEPTANCE=1 env var. Closing per ship-recovery agent's analysis 2026-05-25."*

PR #6 (PR 51) was closed in favor of PR #16, which delivered the identical fix (`fix(dcfr_vector): size next_reach by player_hands not opp_hands`) and was merged 2026-05-26 02:32:12Z.

---

## Why no clean tag boundary exists

The bundle PRs were merged into `origin/main` interleaved with v1.7.2 (CI hardening) and v1.8 (SIMD) work. Per `gh pr list --state merged` chronology:

| Merged-at (UTC) | PR | Lane |
|---|---|---|
| 2026-05-26 02:32:12 | #16 | v1.7.1 bundle (PR 51) |
| 2026-05-26 02:32:58 | #17 | doc cleanup |
| 2026-05-26 02:43:17 | #27 | ship script harden |
| 2026-05-26 02:43:36 | #21 | **v1.7.2 CI release workflow** |
| 2026-05-26 02:43:42 | #22 | **v1.7.2 CI hardening Guards B + C** (PR 60 equivalent) |
| 2026-05-26 02:46:25 | #23 | **v1.8 Phase 1 discount SIMD** |
| 2026-05-26 02:51:23 | #29 | ship script harden |
| 2026-05-26 02:53:52 | #31 | ship script harden |
| 2026-05-26 02:58:23 | #28 | build script harden |
| 2026-05-26 02:58:35 | #30 | **v1.8 cross-platform SIMD smoke test** |
| 2026-05-26 02:59:20 | #5 | v1.7.1 bundle (PR 50) |
| 2026-05-26 02:59:46 | #8 | v1.7.1 bundle (PR 52) |
| 2026-05-26 03:00:03 | #10 | v1.7.1 bundle (PR 55) |
| 2026-05-26 03:00:18 | #12 | v1.7.1 bundle (PR 56) |
| 2026-05-26 03:00:37 | #9 | v1.7.1 bundle (PR 54) |
| 2026-05-26 03:00:54 | #18 | v1.7.1 bundle (PR 59) |
| 2026-05-26 03:01:36 | #35 | **v1.8 AVX2 runtime detect** |
| 2026-05-26 03:01:54 | #14 | v1.7.1 bundle (PR 53b) |
| 2026-05-26 03:02:36 | #15 | v1.7.1 bundle (PR 53c) |
| 2026-05-26 03:24:36 | #41 | **v1.8 Phase 2 update_regret_sum SIMD** |
| 2026-05-26 05:59:33 | #42 | dmg fix |

PR #23 (v1.8 Phase 1 SIMD) was merged **before** PR #5 (the v1.7.1 lead engine fix PR 50). Tagging `v1.7.1` at the last v1.7.1-bundle commit (`49c14211`, PR 53c) would already include v1.8 Phase 1 + AVX2 runtime detect + v1.7.2 CI hardening + cross-platform SIMD smoke test.

There is **no commit on `origin/main` where exactly the 10 v1.7.1 PRs are present and nothing from v1.7.2 / v1.8 is present**.

---

## Why the version was never bumped

Per `docs/leg22_v1_7_1_ship_report.md` and `docs/v1_7_1_retry_3_postmortem.md`: the bundled-ship script `scripts/ship_v1_7_1.sh` was killed by agent execution timeout / smoke-matrix halts five separate times (retries 1-5). Each retry got further into the smoke matrix but none reached the version-bump + tag + push phases. The PRs were then merged individually (the `gh pr merge` path) to land the fixes on `origin/main` without going through the bundled ship script — this was the right call to unblock downstream work, but it skipped the version bump that should have accompanied a v1.7.1 release.

---

## Recommendation: **CLOSE v1.7.1 as obsolete**

The v1.7.1 bundle is shipped — every fix is on `origin/main` — but the *release* (tag + version bump + GitHub release notes) is no longer the right next action because:

1. **Tagging at current HEAD (`728206e`) would mislabel.** That SHA contains v1.7.2 CI release workflow, v1.7.2 CI hardening, v1.8 Phase 1 discount SIMD, v1.8 Phase 2 update_regret_sum SIMD, v1.8 AVX2 runtime detect, v1.8 cross-platform SIMD smoke, plus dmg fixes. A "v1.7.1" tag covering all that work would misrepresent the release scope to anyone reading `git log v1.7.0..v1.7.1`.
2. **Tagging at `49c14211` (PR 53c, last v1.7.1-bundle merge) would also mislabel.** That SHA already contains PR 61 / PR 62 / PR 65 / PR 66 / PR 68 / PR 73 (v1.7.2 CI workflow, ship-process hardening, v1.8 SIMD Phase 1, AVX2 runtime detect, cross-platform smoke).
3. **Version files (`pyproject.toml`, `__init__.py`, `Cargo.toml`) still read 1.7.0.** A retroactive tag without a version-bump commit produces a release whose internal version string disagrees with its tag — confusing for users running `pip show poker_solver`.
4. **v1.8.0 is the natural next release boundary.** It will include every v1.7.1 fix as part of its baseline, plus the v1.7.2 CI hardening and the v1.8 SIMD perf work. Release notes for v1.8.0 should call out the v1.7.1 fixes (e.g., the seven-fix engine + parity-wrapper cluster) as part of the v1.7.0 → v1.8.0 delta.

### Action plan

1. **Do not tag `v1.7.1`.** Skip directly from `v1.7.0` to `v1.8.0`.
2. **Roll v1.7.1 release notes content into v1.8.0 release notes** (see `docs/v1_7_1_release_notes_template.md` for the §`Fixed -- engine` / `Fixed -- Brown parity wrapper` / `Fixed -- test renderer` / `Changed -- acceptance test framing` sections; preserve them under v1.8.0's "Engine + parity-wrapper fixes carried from the v1.7.1 bundle" subsection).
3. **Roll v1.7.2 CI hardening into v1.8.0 release notes** as well (PR 62 release workflow, PR 65 Guards B + C, PR 66 build script bootstrap).
4. **Close the script.** `scripts/ship_v1_7_1.sh` is now obsolete; either delete it or move to `scripts/archive/` with a leading comment that explains the closure.
5. **Optional GitHub Milestone closure.** If a `v1.7.1` milestone exists on GitHub, close it with the note: *"Bundle shipped piecewise on `main`; release folded into v1.8.0 because v1.7.2 CI hardening and v1.8 SIMD work were merged before the v1.7.1 ship script could complete. See `docs/v1_7_1_tag_decision_2026-05-26.md`."*

### Optional fallback — `v1.7.1-bundle-shipped` annotated tag

If a milestone marker is desired for git archaeology without a formal release:

```
git tag -a v1.7.1-bundle-shipped 49c14211 -m \
  "Marker: v1.7.1 engine + parity-wrapper bundle effectively shipped on main.

   All 10 bundle PRs (50, 51, 52, 54, 55, 56, 53b, 53c, 59, 60) merged into
   origin/main between 2026-05-26 02:32 and 2026-05-26 03:02. No version
   bump committed; no GitHub release created. v1.7.1 superseded by v1.8.0.

   See docs/v1_7_1_tag_decision_2026-05-26.md."
```

This is **NOT a release tag** — no GitHub release artifact, no version-string change. It exists only so `git log v1.7.0..v1.7.1-bundle-shipped` returns the bundle delta for future archaeology. Recommend deferring this unless the user specifically requests it.

---

## Why not TAG

For completeness, the TAG path was considered and rejected:

- **TAG at HEAD (728206e):** rejected. Includes v1.7.2 CI hardening + v1.8 Phase 1 + v1.8 Phase 2 + v1.8 AVX2 runtime detect + dmg fixes. Misrepresents release scope.
- **TAG at 49c14211 (last bundle PR by merge time):** rejected. Includes v1.7.2 CI release workflow (PR 62), v1.7.2 CI hardening (PR 65), v1.8 Phase 1 SIMD (PR 61), build script bootstrap (PR 66), AVX2 runtime detect (PR 68), v1.8 cross-platform SIMD smoke (PR 73). Misrepresents release scope.
- **TAG at a synthetic merge-base SHA:** rejected. Would require cherry-picking only the 10 bundle PRs onto a new branch and tagging — equivalent to re-running the failed ship script. Not worth the risk for a release that's already functionally shipped.
- **Version bump commit + tag at HEAD:** rejected. Same misrepresentation problem as bare TAG at HEAD, plus a "bump to 1.7.1" commit applied on top of 1.8-feature commits is not semantically sound (the codebase is currently 1.8-feature-complete-in-progress).

---

## Action taken by this agent

- **None on the repo.** This is a read-only audit + report.
- **Decision rendered: CLOSE v1.7.1 as obsolete.**
- **No tag created. No version bump. No GitHub release.**

The user can:
1. Accept this recommendation and proceed with v1.8.0 planning (folding v1.7.1 fixes into v1.8.0 release notes).
2. Override and request the optional `v1.7.1-bundle-shipped` annotated tag for archaeology.
3. Override and request a synthetic v1.7.1 branch + tag (re-runs the failed ship script's intent on a clean branch). Not recommended — the bundle is already on `main`.

---

## State at a glance

| Item | Value |
|---|---|
| Origin HEAD | `728206e` (post-dmg-fix PR 78) |
| Latest tag | `v1.7.0` (LIVE) |
| Latest GitHub release | `v1.7.0` (2026-05-23) |
| v1.7.1 tag | **does not exist** |
| v1.7.1 release | **does not exist** |
| v1.7.1 bundle on `main` | **10/10 effectively present** (PR 60 via PR #22 supersession) |
| `pyproject.toml` version | `1.7.0` (unchanged) |
| `poker_solver/__init__.py` `__version__` | `"1.7.0"` (unchanged) |
| `crates/cfr_core/Cargo.toml` version | `"0.7.0"` (unchanged) |
| `CHANGELOG.md` latest entry | `[1.7.0] - 2026-05-23` |
| Next release boundary | **v1.8.0** (SIMD perf release; will inherit v1.7.1 fixes) |
