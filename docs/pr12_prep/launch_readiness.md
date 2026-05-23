# PR 12 launch-readiness verification

**Reviewer:** drift check before launch (no implementation context required)
**Scope:** verify pre-drafted prompts in `docs/pr12_prep/` are consistent with current state of `integration` tip
**Verdict:** **READY-WITH-PATCHES** (stretch-goal-grade; PR 12 is post-v1 per PLAN.md §2, so this verification does not block v1)

---

## 1. Per-check results

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | `≈ approximate equilibrium` badge mandatory + unsuppressible on **every** surface (CLI, UI, library) | PASS | spec §6.3 locks badge text + tooltip verbatim; §9 #10 forbids any flag to disable; agent_c_prompt.md §1+§2 enforces with tests for `range_matrix.py`, `library_browser.py`, CLI banner; agent_b_prompt.md §9 hardcodes the 3-line `===` banner in CLI; locked at "load-bearing UX commitment" |
| 2 | Theoretical honesty cites Pluribus + Gibson 2013 (IDSD only, NOT Nash convergence) | PASS | spec §3.1 #4 cites Gibson 2013 for IDSD elimination, p. 2 of Pluribus for "no polynomial-time algorithm" + Lemonade Stand Game; §3.1 #3 cites p. 1 of Pluribus for "Nash playing does not guarantee not-losing in expectation" outside 2p0s; §13 fully indexes papers (`pluribus_brown_2019_science.pdf`, `gibson_2013_regret_minimization.pdf`, `zinkevich_2008_cfr_nips.pdf`); papers confirmed present in `references/papers/` |
| 3 | LCFR + Pluribus 95%-pruning recipe explicitly locked | PASS | spec §3.2 cites Pluribus p. 3 verbatim; §9 #7 locks LCFR for iterations 1..t_cutoff with default `t_cutoff = T // 2`; §9 #8 locks 95% pruning probability + `prune_threshold = -300_000`; §2 explicitly rejects DCFR_{1.5, 0, 2} for 3-handed; agent_b_prompt.md §4-§5 enforces in code with `lcfr_cutoff` + `prune_prob` parameters |
| 4 | Per-pair BR (NOT "exploitability") for n-player; framed correctly | PASS | spec §3.3 + §7.3 lock three per-pair `BR_gap_p` numbers, never summed, never called "exploitability"; §9 #4 enforces with grep gate in `scripts/check_pr.sh`; agent_b_prompt.md §2 has hard-gate string-literal audit; field name `br_gap` (not `exploitability`); §3.4 forbids the bare word "exploitability" |
| 5 | 128/64/32 abstraction tier (tighter than HUNL default 256/128/64) | PASS | spec §5.1 locks default 128/64/32; §5.2 documents the tier table with memory estimates (~6-10 GB / ~3-5 GB / ~1-2 GB); §5.3 reuses PR 4's `precompute-abstraction --bucket-counts 128,64,32` unchanged — no new card abstraction code |
| 6 | Card abstraction TURN-coverage strategy inherits PR 4 patterns + autosize knobs | PASS-WITH-NOTE | PR 4's abstraction in `poker_solver/abstraction/buckets.py` has `Street.TURN` with 4-card boards confirmed; `precompute.py` confirms "autosize-truncated abstraction" support; spec §5.3 explicitly says PR 12 calls existing CLI unchanged with new bucket counts. **Note:** spec does not explicitly mention "autosize knobs"; relies on tier table in §5.2 + `MemoryProbe` fallback from PR 5 §7.7. Adequate for stretch goal |
| 7 | Side-pot math fixtures (TDA rule examples) present | PASS | spec §9 #1 lists 5 required test cases (equal stacks, unequal stacks, one folded, tie split, odd-chip floor/ceiling); cites TDA / WSOP rule set; agent_a_prompt.md "Critical correctness item 1" makes this owner-explicit with the same 5 cases + algorithm sketch; §10.3 ranks it as "the most likely bug class"; audit_prompt.md §3 + §15 lists it as audit focus |
| 8 | 3-seed convergence stability diagnostic | PASS | spec §3.3 + §7.4 lock 3 seeds `(0, 1, 2)`; `StabilityReport` dataclass with `pairwise_max`, `pairwise_mean`, `l1_per_infoset`; soft assertion `pairwise_max < 0.05`; failure → extra badge line "⚠ stability degraded" (not auto-fail); agent_b_prompt.md §8 enforces determinism; agent_c_prompt.md §5+§9 has the warning UI + determinism test |
| 9 | No external solver validation required (MonkerSolver opt-in only) | PASS | spec §7.1 explicitly states PioSolver is HU-only; GTOW postflop multiway not covered (Feb 2026); §7.5 makes MonkerSolver opt-in via `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`; §10.4 mitigates with structural sanity + stability + intuition gauntlet; agent_c_prompt.md §14 documents the JSON fixture format; no bundled data (license) |
| 10 | Build on PR 9 architecture (multiway_solver.py extends HUNL postflop solve) | PASS-WITH-NOTE | spec §6.1 locates new code at `poker_solver/multiway_solver.py` mirroring `hunl_solver.py` (PR 5); routing branch in `solver.py` per §9 #5. **Note:** PR 9 is HUNL **preflop** in PLAN.md §2 trajectory; PR 12 is explicitly postflop-only and reuses PR 5's `solve_hunl_postflop` pattern. PR 12 builds on PR 5 (postflop) + PR 4 (abstraction) + PR 1/6 (DCFR/multiway Rust port) — not "on top of PR 9" specifically. Spec correctly references PR 5 as the structural template. Brief's phrasing slightly off; spec is correct. |

---

## 2. Top 3 findings

### Finding 1 — All ten checks pass; framing discipline is exceptional

The spec's defining quality is its theoretical honesty (§3 is a full page citing Pluribus paper page numbers + Gibson 2013 + Daskalakis-Goldberg-Papadimitriou + Zinkevich). Every output surface gets the "≈ approximate equilibrium" badge with locked text. The string-literal audit in §9 #4 is enforced by an actual `grep` command in `scripts/check_pr.sh`, not just spec text. The unsuppressibility of the badge is called out three times (§1, §6.3, §9 #10, audit_prompt.md focus area 1). This is exemplary work for a post-v1 stretch goal.

### Finding 2 — Pre-PR-12 infrastructure already supports the additive generalization

`hunl.py` line 172-173 confirms current state is `tuple[bool, bool]` for `folded`/`all_in` (2-player tuples), and line 223 confirms `num_players: int = 2` already exists as a config field (presumably from a stub or prior planning). Agent A's "strictly additive on N=2" contract is achievable: the data-shape generalization to `tuple[..., ...]` is a clean rename. `_post_blinds_2p()` and `_post_blinds_3p()` route via `num_players`; `NotImplementedError` for N>=4 is unambiguous. PR 4's `Street.TURN` 4-card-board logic and `precompute-abstraction` CLI work unchanged for tighter bucket counts.

### Finding 3 — Minor drift: brief said "build on top of PR 9"; spec builds on PR 5

Brief check 10 says PR 12 extends "HUNL postflop solve" via `multiway_solver.py`. The spec correctly locates this template at `hunl_solver.py` (PR 5), not PR 9 (HUNL preflop). PR 9 is unrelated to PR 12 mechanically — PR 12 is postflop-only and explicitly out-of-scope for preflop (§2). The spec's references are correct; the brief's phrasing is a minor wording slip. **No action required.**

Other minor observations:

- **UI files don't exist yet.** `ui/views/range_matrix.py`, `ui/views/run_panel.py`, `ui/views/library_browser.py` are forward references to PR 10a/10b/11 work. PR 11 launch-readiness already confirmed PR 10a leaves `library_browser.py` as a stub. PR 12 cannot start UI integration (Agent C scope) until PR 10b + PR 11 land. **Expected for stretch-goal launch order; not a defect.**
- **PR 12 status in PLAN.md** is "📝 spec only — no impl prompts; deferred." After this readiness check, prompts exist but PLAN.md should be updated to "📋 spec'd + prompts ready" when v1 ships. Cosmetic; track separately.
- **Effort estimate (§11): 6–12 weeks** for a single PR is the longest single PR in the roadmap by 2-3×. §12 #4 raises the question of splitting into PR 12 + PR 12.5 (game state vs solver). Decision deferred to user post-PR-11.
- **`HUNLConfig.num_players` field already exists at line 223** but current behavior is unclear — line 172-173 still uses fixed 2-tuples. Either Agent A's work is partially started, or the field is a stub awaiting PR 12. Recommend Agent A audits the existing field semantics before generalizing.

---

## 3. Verdict + stretch-goal launch suitability

**Verdict: READY-WITH-PATCHES.**

The patches are minor:
1. Sync brief's wording on "PR 9 architecture" to actual "PR 5 architecture" (cosmetic; spec is correct).
2. Agent A should clarify current `num_players` field state at `hunl.py:223` before generalizing (avoid silent-conflict refactor).
3. Acknowledge UI work blocks on PR 10b + PR 11 landing first (sequencing; expected).

**Stretch-goal readiness after PR 11:** YES. PR 12 is officially post-v1, and the spec's quality (especially §3 theoretical honesty) is the highest in the roadmap on framing discipline. The 6-12 week estimate is realistic; splitting into PR 12 (Agent A only) + PR 12.5 (solver + UI) per §12 #4 is the recommended risk reduction if PR 11 wallclock runs long. No blockers; safe to fire when PR 11 ships and Agent A's prerequisite generalization on `hunl.py` can begin.
