# Autonomous Burst Release Plan

## 1. Current state recap

v1.0.0 GA tagged at `bbb4395` (PR 11; library + macOS .dmg). v0.6.1 at
`67760c7` (PR 10a.5 UI conformance follow-up) lives on integration awaiting
the split-script cutover to public main. v0.5.x closed at v0.5.2 (PR 4.5
audit-debt sweep). Two PRs are mid-flight: PR 8 (NEON SIMD + cache layout
+ PCS — real kernel speedups, end-to-end flat, 10x gate not met due to
HashMap bottleneck) and PR 9 (HUNL preflop both tiers — implementer still
running, audit staged). v0.6.2 backlog is design-analyzed only.

## 2. PR 8 versioning recommendation: **v1.0.1 (PATCH)**

Ship as PATCH. PR 8 adds internal Rust modules (simd.rs, layout.rs, pcs.rs)
but no user-facing API change and no measurable end-to-end speedup — the
HashMap bottleneck swallowed the kernel gains. CHANGELOG cadence shows
MINOR bumps reserved for new public surfaces (v0.6.0 ui, v0.5.0 Rust port);
PATCH absorbs internal-only changes (v0.5.1 parity harness, v0.5.2 audit
sweep). Honoring the "no extrapolation" rule, we don't get to claim a perf
MINOR when the measured delta is flat at the surface. Ship the infra; let
the perf bump justify itself when the HashMap follow-up lands.

## 3. PR 9 versioning recommendation: **v1.1.0 (MINOR)**

Ship as MINOR. PR 9 closes the public OSS preflop gap — substantive new
capability (preflop tier in both Python and Rust). MAJOR is overclaim:
public API stays additive (no break of the v1.0.0 contract), and v1.0.0
was already framed as the "v1 scope = HUNL postflop + preflop together"
milestone — preflop is a fill-in of locked v1 scope, not a v2 redefinition.
Cadence precedent: v0.4.0 (PR 4 + PR 5 — postflop solver landing) was
MINOR for an analogous capability landing. v1.1.0 matches that pattern.

## 4. Ship order: **PR 8 → PR 9 (separate releases)**

PR 8 ships first as v1.0.1, PR 9 follows as v1.1.0. Three reasons:
(a) **honest accounting** — PR 8's "real kernel speedups, end-to-end flat"
needs its own CHANGELOG entry so the perf-infra baseline is documented
without being smuggled into a feature release; (b) **smaller blast radius**
— if PR 9 audit surfaces a preflop regression, PR 8's already-shipped
perf-infra is untouched and bisectable; (c) **release cadence** — the
project ships frequently (eight versions in the v0.x → v1.0.0 arc); the
ceremony cost is low and the narrative is cleaner. Batching as one v1.1.0
would conflate "perf infra landed" with "preflop landed" and bury PR 8's
honest verdict.

## 5. v0.6.2 scope decision: **DEFER from this burst**

Out of scope. Items 2+3 are audit-followup quality (clamp policy + dead-code
ETA wiring), not new-feature quality. Design analysis is done but the
implementation needs a production-ETA measurement pass that depends on
PR 10b (real-solver bindings, not in this burst). Folding v0.6.2 into the
burst trades clean post-PR-9 release narrative for a small mechanical PR
that has a natural home post-PR-10b. Park in the v0.6.2 backlog
(`docs/pr10a_5_prep/v0_6_2_backlog.md`) and revisit after PR 10b lands.

## 6. Cutover sequencing: **Run NOW**

Execute the dual-channel cutover (D-H) immediately — publish v0.6.1 to
public main first, then ship PR 8 (v1.0.1) and PR 9 (v1.1.0) against the
already-cleaned main. Cutover is already in motion (`c8aa2a2` Option C
landed; split-script committed at `c50f4dd`; backup remote being wired).
Batching the cutover after PR 8 + PR 9 land would mean one larger public
push containing three orthogonal concerns (publishing infra change + perf
infra + preflop capability) — harder to audit per the public-repo-hygiene
rule.

## 7. TL;DR

Cutover now, ship PR 8 as v1.0.1, then PR 9 as v1.1.0; defer v0.6.2.
