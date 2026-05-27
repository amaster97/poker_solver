# Outside-Observer Audit — Post-Polish Pass

**Date:** 2026-05-23 (re-audit after metadata polish)
**Lens:** Same as prior audit — developer landing cold, no prior context.
**Method:** Read-only via `gh` CLI. No content modified.
**Predecessor:** `docs/outsider_view_audit.md` (NEEDS-POLISH verdict).

---

## 1. What changed since the prior audit

The metadata-polish agent's fix has **LANDED on GitHub**. Verified via
`gh repo view amaster97/poker_solver --json description,repositoryTopics`:

**New description (≈340 chars, expansive and accurate):**

> "MIT-licensed two-tier (Python + Rust via maturin) HUNL Texas Hold'em
> GTO solver. Tabular DCFR with vector-form CFR for true range Nash;
> preflop push/fold + postflop tree solving; aggregator vs Nash
> range-vs-range APIs; NiceGUI GUI + macOS .dmg + CLI. Card abstraction
> 256/128/64 (flop/turn/river); diff-tested vs Brown's MIT reference."

**Compared to the prior stale description** ("Texas Hold'em equity
solver in pure Python: hand evaluator, Monte Carlo equity, range parser,
CLI."), this:
- Names the MIT license up front (the project's licensing edge)
- Names the two-tier Python+Rust architecture
- Names HUNL, DCFR, vector-form CFR, push/fold, range Nash
- Names the GUI + `.dmg` + CLI surfaces
- Names the card abstraction depth
- Names the differential-testing oracle (Brown's reference)

**New topics (12 keywords, all meaningful):**

`cfr`, `dcfr`, `gto`, `holdem`, `maturin`, `nash-equilibrium`, `poker`,
`poker-solver`, `pyo3`, `python`, `rust`, `texas-holdem`.

These cover the main discoverability channels: poker terms (`poker`,
`poker-solver`, `holdem`, `texas-holdem`), GTO/CFR terms (`gto`, `cfr`,
`dcfr`, `nash-equilibrium`), and tech stack (`python`, `rust`, `pyo3`,
`maturin`).

**Homepage URL:** Still not set. Low impact — a homepage URL would
just point back at the repo or a docs subpage, and the description
already conveys the project. Acceptable to leave.

---

## 2. Updated 30-second first-impression

A developer landing cold on `github.com/amaster97/poker_solver` now sees:

- **Description:** Conveys the full scope in one line (two-tier
  Python+Rust HUNL GTO solver with range Nash, GUI, .dmg, CLI). No
  longer mistakable for "yet another equity calculator on PyPI."
- **Topics:** 12 relevant keywords. The repo is now discoverable via
  topic-search (`#poker-solver`, `#cfr`, `#gto`, etc.).
- **Latest release pill:** `v1.7.0` (today's date).
- **License pill:** MIT.
- **Activity:** 5 releases on 2026-05-23 (v1.4.3 → v1.7.0). Recent
  commits with substantive multi-paragraph messages.

**30-second verdict:** Now passes the cold-developer credibility test
on the GitHub landing surface. A searcher filtering by description or
topic would recognize this as a serious HUNL solver, not bounce.

---

## 3. Discoverability assessment

**Before polish:** Description undersold the project ~10x; no topics →
zero topic-search reach.

**After polish:** Description fronts the differentiated positioning (MIT
+ two-tier + range Nash + GUI). Topics cover the standard search
vectors a developer would use:
- "github poker solver" → topics `poker-solver`, `gto`, `cfr`
- "open source CFR" → topics `cfr`, `dcfr`, `nash-equilibrium`
- "rust python pyo3" → topics `rust`, `python`, `pyo3`, `maturin`

This is a meaningful discoverability lift from baseline.

---

## 4. Remaining gaps (PR-gated, will resolve on merge)

These were flagged in the prior audit and are unchanged by the metadata
polish — they require the open PRs to merge:

| Gap | PR that resolves | Severity |
|---|---|---|
| README cites `docs/dmg_v1_4_0_smoke_verification.md` (404 on GitHub) | **PR #4** (`pr-49-readme-broken-ref-cleanup`) | High — load-bearing Known issues block |
| README cites `docs/v1_6_1_dryrun_verification.md` (404 on GitHub) | **PR #4** (same) | High — same block |
| USAGE.md still at v1.4.x baseline (release notes point to non-existent §5.6) | **PR #2** (`pr-48-usage-v1-7-0-semantics`) | Medium — breaks v1.7.0 release-notes forward-ref |
| USAGE.md §2 still says `.dmg` is "recommended for non-developers" (contradicts README) | **PR #2** (same) | Medium — internal doc inconsistency |
| USAGE.md §8 stale ("PR 9 ships in v1.1.0" / "3-handed post-v1") | **PR #2** (same) | Low — historical wording |
| `.dmg` installer doesn't work on clean Mac (nicegui bundle + arch + version stamp) | **PR #3** (`pr-44-dmg-packaging-fix`) | High — but explicitly Known-issued; honest framing protects credibility |
| README "latest release v1.6.0" lags actual v1.7.0 | Not yet PR'd | Low — README has "v1.7.0 in flight" wording so reader can infer |

**All three open PRs are well-formed:** conventional-commits titles,
scope-controlled bodies, no abandoned drafts visible. The PR list view
is itself a credibility signal.

---

## 5. Comparison against prior audit's recommendations

The prior audit identified **four high-impact 5-min fixes**:

| Recommendation | Status |
|---|---|
| Update the repo description | **DONE** (this polish pass) |
| Merge PR #4 (broken README cross-refs) | **OPEN** — not yet merged |
| Add GitHub topics | **DONE** (12 topics added) |
| Set homepage URL | Not done — acceptable to skip (low impact) |

**2 of 4 are landed.** The two remaining are PR-gated.

The prior audit identified **two high-impact 1-hour fixes** (PR #2
merge + USAGE.md install-path softening). Both still pending — these
are the next dependencies.

The prior audit identified **one polish item for v1.8/v2** (PR #3 .dmg
fix). Still pending; explicitly Known-issued so doesn't block share-ready.

---

## 6. Honesty assessment (Known issues block in README)

The README's Known issues section remains accurate:

- `.dmg` doesn't work on clean Mac — **TRUE** (PR #3 in flight)
- v1.5.0 Brown acceptance test FAILS at deep-cap spots — **TRUE**
  (investigation in flight per `docs/v1_6_1_dryrun_verification.md`,
  which is 404'd publicly but the *claim* in the README is accurate)
- `Range` fractional frequencies not supported — **TRUE** (v1.8+ scope)
- CLI ergonomic gaps (pushfold subcommand, river hero-vs-range, parity)
  — **PARTIALLY STALE**: per v1.7.0 release notes, PR 39 *added* these
  subcommands. README is one revision behind. Not a credibility killer
  (reader can find v1.7.0 release notes via the Releases page) but a
  next-doc-pass cleanup target.

**Net:** Known issues remain mostly accurate; one bullet (CLI
ergonomic gaps) is mildly stale. The honest posture is preserved.

---

## 7. Recommended user action

**Single action: merge the 3 open PRs.**

| PR | Effect on share-readiness |
|---|---|
| **PR #4** (broken cross-refs) | Removes 2 GitHub 404s from load-bearing Known-issues section |
| **PR #2** (USAGE.md v1.7.0) | Closes the v1.7.0 release-notes → USAGE.md §5.6 forward-reference; aligns USAGE.md install-path recommendation with README |
| **PR #3** (.dmg packaging) | Lets the Known-issues `.dmg doesn't work` block come out of the README (or move from "BROKEN" to "experimental, see install guide") |

**After all three merge:** Repo is **fully SHARE-READY** — credible
landing surface, no public broken cross-refs, internally consistent
docs, and the `.dmg` story upgrades from "doesn't work" to "experimental
but functional."

**If only PR #4 + PR #2 merge** (PR #3 deferred): Still SHARE-READY for
source-install users. The `.dmg` Known-issues block remains, but it's
the honest framing the user has explicitly chosen.

---

## 8. Final verdict

**SHARE-READY for the GitHub landing surface** (description + topics +
release pill + activity signal + license).

**NEEDS-POLISH for full documentation consistency** (3 open PRs to
merge, all already well-formed and ready).

A developer landing on the repo today via Google or GitHub topic search
would:
- **See an accurate, expansive description** that conveys the niche
  (MIT + two-tier + range Nash + GUI + DCFR + Brown-oracle diff-tested)
- **Find the repo via topic search** for `poker-solver`, `cfr`, `gto`,
  `nash-equilibrium`, etc.
- **Trust the activity signal** (5 releases today, substantive commits)
- **Trust the architecture** (README + DEVELOPER.md openly explain the
  two-tier setup; not a fiction)
- **Trust the honesty** (Known issues stated up front; deep-cap
  acceptance failure openly flagged)
- **Hit 2 GitHub 404s** if they click the most-cited Known-issues
  references (until PR #4 merges)
- **Land on USAGE.md and find it v1.4.x-vintage** (until PR #2 merges)

The metadata polish closed the biggest first-impression gap (the stale
description that undersold the project ~10x). What remains is doc-layer
consistency that resolves on the 3 open PRs.

**Verdict shift:** NEEDS-POLISH → **SHARE-READY (landing surface)** /
NEEDS-POLISH (doc consistency, PR-gated). One merge wave away from
fully SHARE-READY.

**Recommendation to user:** Ship the 3 open PRs (PR #4 first — it's the
smallest and removes the public 404s; then PR #2; then PR #3 if
.dmg-rebuilt artifact is ready). After PR #4 + PR #2, the repo is
fully share-ready by any cold-developer credibility standard.
