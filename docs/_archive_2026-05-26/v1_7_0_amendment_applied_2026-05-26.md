# v1.7.0 Release Notes Amendment — Applied (2026-05-26)

**Agent:** v1.7.0-release-amendment (Stage-3 autonomous; doc-only append).
**Source spec:** `docs/v1_7_0_release_consistency_2026-05-26.md` §3.
**Method:** `gh release edit v1.7.0 --notes-file <tmp>` — single append of dated "Post-publication notes" section. No inline rewrites of the original release-time narrative.

---

## Result

- **Release URL:** https://github.com/amaster97/poker_solver/releases/tag/v1.7.0
- **Tag:** `v1.7.0` (unchanged)
- **Title:** `v1.7.0: aggregator->vector wiring + CLI subcommands` (unchanged)
- **Asset list:** unchanged (no asset operations performed)

## Before / after body size

| Metric | Before | After | Delta |
|---|---|---|---|
| Bytes | 3433 | 4556 | +1123 |
| Lines | 57 | 71 | +14 (under 20-line cap) |

## Original "stale" line — PRESERVED

Per the spec's "do not rewrite history" constraint, the original status-notes line at L13 was left untouched:

> - v1.6.1 engine bundle: HELD pending acceptance gate redefinition (deep-cap Brown apples-to-apples reveals architectural divergence in payoff convention)

The amendment supersedes it via the dated appendix at the bottom, not by editing the original.

## Amendment text added (verbatim, appended after `See [CHANGELOG.md](CHANGELOG.md) for full details.`)

```markdown
---

## Post-publication notes (2026-05-26)

Three days after v1.7.0 shipped, the release roadmap was restructured. Readers landing here from search engines or release lists should know:

- **v1.6.1 hold has been LIFTED.** The hold listed above ("v1.6.1 engine bundle: HELD pending acceptance gate redefinition") was lifted on 2026-05-26 per the ship review. See `docs/v1_6_1_ship_hold_review_2026-05-26.md`.

- **A83 deep-cap divergence cause corrected.** The status note above attributed the divergence to "architectural divergence in payoff convention." The actual cause is **Nash multiplicity at deep-cap indifference manifolds** (empirically confirmed via three independent DCFR-math audits + a Track A bench). It is a design difference vs. Brown/Pluribus, not a bug. See `docs/a83_nash_multiplicity_confirmed_2026-05-26.md`.

- **Next release boundary is v1.8.0.** v1.6.1 and v1.7.1 will not ship as separate tagged releases; their fixes shipped piecewise on `main` and are folded into v1.8.0. See `docs/v1_7_1_tag_decision_2026-05-26.md`.

The `solve_range_vs_range_nash` API-semantics note above remains accurate.
```

## Verification

`gh release view v1.7.0 --json body --jq '.body' | tail -20` confirms the appendix is present at the tail of the release body. `grep` confirms both the original "v1.6.1 HELD" L13 line and the new "hold has been LIFTED" L64 line coexist.

## Audit-clear checklist

- [x] Additive amendment (no original-narrative edits)
- [x] Doc-only (release notes; no code or asset changes)
- [x] Under 20-line cap (14 lines added)
- [x] Three required documents linked in the amendment
- [x] Hold-lift, Nash-multiplicity correction, and v1.8.0 boundary all addressed
- [x] Tag / name / assets unchanged

Stage-3 autonomous-eligibility satisfied. No further action required.
