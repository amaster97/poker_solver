# v1.7.0 GitHub Release — Consistency Audit (2026-05-26)

**Auditor:** v1.7.0-release-consistency agent (read-only audit; ~12 min budget)
**Scope:** Audit the published v1.7.0 GitHub Release body for stale claims vs. tonight's narrative (v1.6.1 hold-lift, v1.7.1-as-obsolete, A83 closure, v1.8 SIMD ~1.0× measured).
**Release captured:** `v1.7.0` — published `2026-05-23T23:06:07Z` — title: *"v1.7.0: aggregator->vector wiring + CLI subcommands"*.

---

## TL;DR — verdict: **NEEDS-UPDATE (one clearly stale line)**

One stale claim found, one borderline. Recommended action: **single "Post-publication notes" amendment at the bottom** of the release body (Stage-3 doc-cleanup autonomous-eligible), NOT inline edits to the original release-time narrative. Rationale: original release-time prose is historically accurate as of 2026-05-23; tonight's amendments belong in a clearly-dated appendix.

---

## 1. Tonight's narrative (reference points)

For each of the user's four explicit drift vectors, the published-at-ship state vs. tonight's state:

| Drift vector | Published-at-ship (2026-05-23) | Tonight (2026-05-26) | Source-of-truth |
|---|---|---|---|
| v1.7.1 status | Bundle in flight, ship script being retried | **CLOSED as obsolete; folded into v1.8.0** | `docs/v1_7_1_tag_decision_2026-05-26.md` |
| v1.6.1 engine bundle | HELD pending acceptance gate redefinition | **HOLD LIFTED; shipped piecewise on `main`; folded into v1.8.0** | `docs/v1_6_1_ship_hold_review_2026-05-26.md` |
| A83 deep-cap divergence | Investigation in flight (deep-cap Brown apples-to-apples) | **CLOSED: Nash multiplicity, design divergence, NOT a bug** (3 audits + empirical confirm) | `docs/a83_validation_2026-05-26.md` |
| v1.8 SIMD speedup | Not mentioned in v1.7.0 release | (claimed 4-8× in v1.8 draft; measured ~1.0×) | `docs/v1_8_simd_perf_benchmark_2026-05-26.md` |

---

## 2. Stale-claim scan against v1.7.0 release body

I scanned the full body (captured via `gh release view v1.7.0 --json body`). Hits below.

### 2.1 Stale claim (high-confidence)

**Line in body (under `## Status notes`):**
> - v1.6.1 engine bundle: HELD pending acceptance gate redefinition (deep-cap Brown apples-to-apples reveals architectural divergence in payoff convention)

**Status:** **STALE**. Hold has been lifted as of tonight (2026-05-26). The "architectural divergence in payoff convention" hypothesis was also wrong — the actual cause is Nash multiplicity (indifference manifolds at deep cap), confirmed by 3 independent DCFR audits + empirical Track A bench. See `docs/a83_validation_2026-05-26.md` and `docs/v1_6_1_ship_hold_review_2026-05-26.md`.

**Why this matters:** A reader landing on the v1.7.0 release page today sees "v1.6.1 HELD" and reasonably infers (a) v1.6.1 is the next live release, (b) there's an open hold blocking it, (c) the cause is a payoff-convention design bug. All three inferences are now wrong. The release boundary skips v1.6.1 / v1.7.1 entirely and goes to v1.8.0.

### 2.2 Borderline (still factually true, but reframed)

**Line in body (under `## Status notes`):**
> - PR 44 .dmg packaging fix: verified on disk; ready for Gate 5 attachment

**Status:** **STILL TRUE BUT SUPERSEDED**. PR 44 was indeed the .dmg fix and Gate 5 attached for v1.6.0 (`docs/gate_5_v1_6_0_dmg_attached.md`). Tonight's narrative is that .dmg is now a recurring release deliverable (the v1.8.0 prep mentions Poker-Solver-1.8.0-arm64.dmg pipeline). The line as written is not wrong — it's a release-time snapshot — but it implies "Gate 5 still pending attachment" which is no longer accurate for the v1.6.0 boundary.

**Verdict:** *Borderline*. The line is historically accurate. I do not recommend inline correction.

### 2.3 Not stale — no false claim found

| User-flagged drift | Found in v1.7.0 body? |
|---|---|
| "v1.7.1 in flight / coming" | **No** — body does not mention v1.7.1 at all |
| "4-8× SIMD speedup" | **No** — body does not mention SIMD perf at all (that's a v1.8.0-draft issue, not v1.7.0) |
| "A83 investigation in flight" | **Partial** — the v1.6.1 HELD line implies open investigation; covered by §2.1 above |

The body's "Post-release validation findings (2026-05-23 late)" section about `solve_range_vs_range_nash` class-label vs combo-level semantics is a separate API-semantics note from 2026-05-23. It is unrelated to tonight's narrative and remains factually accurate (the class-expansion behavior is real and documented in `USAGE.md` §5.6).

---

## 3. Recommended action

### Recommendation: **Append a single dated "Post-publication notes" section at the bottom of the release body.**

Do NOT inline-edit the original release narrative. The original body is historically accurate as of 2026-05-23 publish time and serves as an archaeology record. The amendment should be a clearly-dated appendix that points readers to v1.8.0.

### Proposed amendment text (for `gh release edit v1.7.0 --notes-file`)

```markdown
---

## Post-publication notes (2026-05-26)

Three days after v1.7.0 shipped, the project's release roadmap has been
restructured. Readers landing here from search engines or release lists
should know:

- **v1.6.1 hold has been LIFTED.** The hold listed above ("v1.6.1 engine
  bundle: HELD pending acceptance gate redefinition") was lifted on
  2026-05-26. Three independent DCFR-math audits + an empirical Track A
  benchmark confirmed the A83 deep-cap divergence is **Nash multiplicity**
  (indifference manifolds at deep cap), not a payoff-convention bug. See
  `docs/a83_validation_2026-05-26.md` and `docs/v1_6_1_ship_hold_review_2026-05-26.md`.

- **v1.6.1 and v1.7.1 will NOT have separate releases.** Both bundles
  shipped piecewise on `main`, and their fixes are folded into v1.8.0
  rather than tagged independently. See `docs/v1_7_1_tag_decision_2026-05-26.md`.

- **Next release boundary is v1.8.0.** v1.8.0 inherits every v1.6.1 +
  v1.7.1 fix as part of its baseline. Release-notes mapping is in
  `docs/v1_8_0_release_notes_DRAFT.md`.

The `solve_range_vs_range_nash` API semantics note above remains accurate.
```

### Why an amendment vs. inline edit

| Option | Pros | Cons |
|---|---|---|
| Inline edit of "v1.6.1 HELD" line | Cleaner final state | Rewrites history; loses release-time context |
| Append "Post-publication notes" (RECOMMENDED) | Preserves history; explicit dated reframe; readable as archaeology | Slightly longer body |
| Do nothing | Lowest effort | Reader of v1.7.0 page is misled about v1.6.1 status |

### Stage-3 autonomous-eligibility

This is a **single-section append** to a release body — no semantic rewrite of the original release narrative. Under the user's Stage-3 doc-cleanup framing (per `feedback_pr10a5_autonomous_commit.md`), this qualifies as a small autonomous amendment. However, since this is a public-facing GitHub release page and the user has explicit public-repo-hygiene rules (`feedback_public_repo_hygiene.md`), I recommend **proposing the text for user review** before pushing via `gh release edit`. The proposed text above is ready to use as-is or with minor edits.

---

## 4. Verdict

- **NEEDS-UPDATE.**
- **One clearly stale line** ("v1.6.1 engine bundle: HELD pending acceptance gate redefinition") — tonight's narrative has lifted the hold and reframed the cause.
- **One borderline line** (PR 44 / Gate 5) — historically accurate; recommend leaving.
- **Recommended:** append a dated "Post-publication notes" section. Proposed text is in §3 above.
- **Action by this agent:** **None on the repo.** This is a read-only audit per the user's READ-ONLY constraint.

---

## Appendix — release-page state at audit time

| Field | Value |
|---|---|
| Tag | `v1.7.0` |
| Title | `v1.7.0: aggregator->vector wiring + CLI subcommands` |
| Published at | `2026-05-23T23:06:07Z` |
| Body length | ~2.8 KB |
| Bodies scanned | full body via `gh release view v1.7.0 --json body --jq '.body'` |
| Stale lines found | 1 high-confidence + 1 borderline |
| Edit recommended | append "Post-publication notes" (~14 lines) |
| Edit method | `gh release edit v1.7.0 --notes-file <path>` (proposed) |
| Action taken | NONE — read-only audit + this report |
