# PR 12 audit pre-prep — anticipated findings & pre-patches

**Date:** 2026-05-22
**Author:** orchestrator pre-stage (audit-anticipation)
**Branch under (future) audit:** `pr-12-three-handed-stretch`
**Mirror of:** `pr7_prep/audit_preprep.md` + `pr8_prep/audit_preprep.md` pattern.
**Scope:** anticipate likely audit findings for PR 12 (3-handed postflop solve — optional / stretch / explicitly approximate) BEFORE PR 12 fires; pre-stage any viable patches; record sequencing.

PR 12 has **not started**. The branch `pr-12-three-handed-stretch` does not exist yet (gated on ALL of PR 1-11 merging to `main` AND v1 being tagged AND user explicitly approving the launch per `fanout_ready.md` §0). This doc can sit idle for months or years. It is anticipation-only.

PR 12 is the **largest single PR in the v1 roadmap** (6-12 week estimate; 2-3× the next-largest), and the **only PR shipping an explicitly approximate solution concept** (per `pr12_spec.md` §1). Honest framing is the deliverable. The audit emphasizes framing discipline equal weight to correctness, per `audit_prompt.md` line 11: *"silent 'Nash'/'GTO'/'exploitability' claims in 3-handed code paths are correctness bugs, not cosmetic issues."*

---

## 1. Likely audit findings (8 user-flagged risks)

### 1.1 "≈ approximate equilibrium" badge mandatory + unsuppressible — **HIGH / must-fix on any omit or suppression path**

Spec: `pr12_spec.md` §1 line 14 ("load-bearing"); §6.3 lines 346-368 (exact text locked); §9 #10 (unsuppressible); `audit_prompt.md` §1.

- Badge on EVERY surface: range matrix panel, library row, CLI stdout banner (3-line `===` borders per §6.3 line 366).
- Exact text + tooltip byte-match (per §6.3 lines 354-363).
- Grep `poker_solver/cli.py`, `ui/views/*.py`, `multiway_solver.py` for `--suppress-badge`, `--quiet-approximate`, `verbose=False`-conditioned skip. Any match → must-fix.
- Hardcoded `if result.num_players >= 3: render` — no boolean override.
- Test: `test_badge_cannot_be_disabled_via_config` (per `fanout_ready.md` §4 line 127).

**Failure mode:** `verbose=True` flag "for expert users" hides the warning; library JSON export omits the badge field. **Severity:** must-fix on every surface (CLI / UI / JSON / repr); non-negotiable per §9 #10.

### 1.2 Per-pair BR (NOT "exploitability") terminology gate — **HIGH / must-fix on any bare term**

Spec: `pr12_spec.md` §3.4 lines 162-166; §7.3; §9 #4 (grep gate); `audit_prompt.md` §2.

Exact grep (`fanout_ready.md` §5 line 134):
```sh
grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ poker_solver/cli.py | grep -v 'best-response\|approximate\|≈\|near-Nash'
```
Expected zero output.

- THREE numbers per solve, NOT summed. Field name `br_gap`, NOT `exploitability` (most common Agent B violation per `fanout_ready.md` line 137).
- Label exact: "≈ best-response EV upper bound (multi-player; NOT Nash exploitability)" per §7.3 line 419.
- Docstring "Nash convergence" without "no" qualifier → must-fix.

**Failure mode:** `MultiwaySolveResult.exploitability: tuple[float, float, float]` "to match HU API". **Severity:** must-fix; single bare "exploitability"/"Nash"/"GTO" in 3p path (outside paper-citing comments) blocks PR per `audit_prompt.md` line 11.

### 1.3 Side-pot math TDA fixtures (load-bearing) — **HIGH / must-fix on any of 5 fixtures**

Spec: `pr12_spec.md` §9 #1 lines 554-573 ("single hardest correctness item"; Pio/postflop-solver/Slumbot all have public side-pot bugs); §10.3; `audit_prompt.md` §3.

`_compute_side_pots(contributions, folded) -> list[SidePot]` helper + 5 fixtures (`fanout_ready.md` §5 lines 142-145):
1. Equal-stack all-in `[50,50,50]` → main pot 150.
2. Unequal `[50,100,150]` → main 150 + side 100 + P2 returns 50.
3. Folded `[50,30(F),100]` → folded's 30 to main; eligible={0,2}.
4. Tie split with remainder by position (SB first postflop).
5. Odd-chip floor/ceiling vs TDA examples.

**Failure mode (most likely):** Fixture 4 — position semantics under-specified in §9 #1; agent picks wrong tiebreak (dealer button vs SB). **Severity:** must-fix on ANY of 5 fixture failures; "most likely bug class" per §10.3.

### 1.4 LCFR (NOT DCFR_{1.5,0,2}) + 95%-pruning at 128/64/32 — **MEDIUM / must-fix if DCFR used**

Spec: `pr12_spec.md` §2 lines 62-65 ("We do NOT use DCFR_{1.5,0,2} for 3-handed"); §3.2; §9 #7-#8; `audit_prompt.md` §6-§7.

- LCFR (DCFR_{1,1,1}) for iters 1..t_cutoff, plain CFR averaging after. Default `t_cutoff = T // 2` per Pluribus p. 3.
- `dcfr_kwargs={'lcfr_cutoff': T//2}` exposed.
- NOT `--dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2` (PR 7 flags illegal for 3p).
- 95%-pruning: `random.random() < 0.95` skip; threshold default `-300_000` cents (§9 #8, §12.8).
- Soft-assertion: per-pair BR gaps moving-average trends down (§7.2 #4).

**Failure mode:** Agent copy-pastes PR 7 DCFR pattern; or pruning disabled "for safety" → §10.5 wallclock risk. **Severity:** must-fix if DCFR_{1.5,0,2} used for 3p (overclaims Pluribus's empirical validation).

### 1.5 `num_players` field exists; `folded`/`all_in` still 2-tuples — Agent A reconciliation — **HIGH / must-fix on N=2 regression**

Spec: `fanout_ready.md` line 5 (load-bearing for entire PR); `pr12_spec.md` §4.1 lines 178-188; §4.2; §8.1; `audit_prompt.md` §11.

- Pre-flight: `c = HUNLConfig(); type(c.folded)` per `fanout_ready.md` §1 line 46.
- If `tuple[bool, bool]` → Agent A must generalize to `tuple[bool, ...]` length=`num_players`.
- Strictly additive on N=2: all PR 3-11 tests pass unchanged.
- `HUNLState` field names + `HUNLPoker` method signatures stable (Agent B/C lock).
- Position 3-handed locked: P0=SB, P1=BB, P2=BTN.

**Failure mode:** Field rename "for clarity" (`folded` → `is_folded`) → cascading break in Agent B/C consumer code; PR 5/10/11 tests fail. **Severity:** must-fix on ANY N=2 regression or field rename breaking consumers.

### 1.6 No external Nash oracle (MonkerSolver optional) — **LOW / should-fix on harness shape**

Spec: `pr12_spec.md` §7.1 (Pio HU-only; GTOW postflop multiway unavailable); §7.5 (Monker opt-in); §12 #3; `audit_prompt.md` §12.

- `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())` per §7.5 line 452.
- NO bundled data (license). Format documented; user populates manually.
- Tolerance: per-infoset L1 < 0.10 (§7.5 line 450).

**Failure mode:** Agent commits sample Monker fixture from a forum post (license unknown). **Severity:** must-fix if any Monker data bundled; should-fix if harness shape wrong (always-skip / always-run-no-fixture).

### 1.7 3-seed convergence stability diagnostic — **MEDIUM / should-fix on threshold or non-determinism**

Spec: `pr12_spec.md` §3.3; §7.4 lines 424-442; §12 #9; `audit_prompt.md` §5.

- `run_stability_diagnostic(config, abstraction, seeds=(0,1,2)) -> StabilityReport`.
- Fields: `seeds`, `strategies`, `l1_per_infoset`, `pairwise_max`, `pairwise_mean`.
- Soft: `pairwise_max < 0.05` on river-only fixture. If exceeds → badge gains "⚠ stability degraded".
- **Determinism:** rerunning same seeds yields same numbers. Test: `test_stability_diagnostic_is_deterministic`.

**Failure mode:** `np.random.default_rng()` without explicit seed threading → non-deterministic. **Severity:** should-fix on threshold drift to 0.10; must-fix if non-deterministic.

### 1.8 Pluribus + Gibson 2013 citations (IDSD, NOT Nash convergence) — **MEDIUM / must-fix on overclaim**

Spec: `pr12_spec.md` §3.1 lines 108-116 (Gibson's strongest result is **iteratively strictly dominated** action elimination, NOT Nash convergence — "*much weaker*"); §7.2 #3; §13; `audit_prompt.md` §16.

- Pluribus cited from `references/papers/pluribus_brown_2019_science.pdf` for LCFR + 95%-pruning recipe.
- Gibson 2013 cited for IDSD elimination ONLY; NOT Nash convergence.
- Docstring grep: any "Gibson proves CFR converges to Nash in n-player" → must-fix overclaim.
- Test: synthetic 3p toy with strictly dominated action; frequency → 0 within ε.

**Failure mode (most likely):** Comment like "Gibson 2013 establishes CFR convergence for n-player games" — OVERCLAIMS; Gibson proves IDSD only; Nash convergence remains open (§3.1 line 90). **Severity:** must-fix on ANY overclaim of Gibson result or LCFR n-player Nash guarantee.

---

## 2. Pre-patches viable BEFORE PR 12 fires

**None.** PR 12 has not started; the branch `pr-12-three-handed-stretch` does not exist (gated on v1 ship + user approval per `fanout_ready.md` §0). There is no diff to patch.

Pre-stage actions already complete (per `pr12_prep/launch_readiness.md` verdict READY-WITH-PATCHES):
- **Reconciliation flag raised:** `hunl.py:223` `num_players` stub vs 2-tuple `folded`/`all_in` known to Agent A; loaded into Agent A's prompt body.
- **Default fan-out pattern:** Pattern B staged (A first, then B+C parallel) per `fanout_ready.md` §3 — reduces interface-drift risk.
- **Default split:** PR 12 = Agent A; PR 12.5 = Agents B+C (per `fanout_ready.md` line 98 — "Default if user silent: split"). Halves single-PR risk.
- **String-literal grep gate hardened:** exact incantation locked at `fanout_ready.md` §5 line 134.
- **Side-pot diagnostic ladder locked:** 5 fixtures pre-specified at `fanout_ready.md` §5 lines 142-145.

No code-level pre-patches are viable. PR 12 audit infra is read-only until A (or A+B+C) produce a diff.

---

## 3. Expected audit verdict

PR 12 is the **highest-stakes PR in the roadmap** for honesty-of-framing — by an order of magnitude over any other PR. The audit will weight framing discipline as heavily as correctness.

**Most likely verdicts (in order of probability):**

1. **READY-WITH-PATCHES** (~45%): minor must-fix on one of:
   - A bare "exploitability" docstring slipped through the grep gate (§1.2).
   - One TDA side-pot fixture fails on the tie-with-remainder case (§1.3 fixture #4).
   - A test asserts the badge text loosely (substring match) instead of exact (§1.1).
   - Gibson 2013 citation slightly overclaimed in one comment (§1.8).
   Resolvable in <1 week.

2. **NOT READY** (~30%): one of:
   - Convergence stability diagnostic fails on river-only fixture (`pairwise_max >= 0.05`); per §3.1 #4 this CAN happen because multi-player CFR has no convergence proof. Mitigation: extend iterations, retune `lcfr_cutoff`, retry. May require a PR 12.5 split if root-cause is algorithmic.
   - Side-pot math wrong on ≥2 of the 5 fixtures (high difficulty; known to be hard).
   - DCFR_{1.5, 0, 2} accidentally used instead of LCFR (copy-paste from PR 7).
   - N=2 path regression breaks PR 5/9/10/11 tests (Agent A reconciliation got a field rename wrong).

3. **READY for commit** (~15%): all 16 audit focus areas pass clean. Only possible if Agent A's reconciliation is textbook AND Agent B nails LCFR + side-pot AND Agent C's badge tests are exhaustive.

4. **READY with must-fix only on stability threshold** (~10%): `pairwise_max < 0.10` (relaxed) but the warning surfaces in the UI badge. Spec-acceptable per §7.4 "soft assertion" framing, but audit will flag for user review.

**Probability the string-literal grep gate fails (at least one bare match):** ~50%. This is the most pernicious surface — agents under load slip "Nash" into a comment or docstring. The grep gate catches it post-hoc; the audit catches it as must-fix.

**Probability the badge is somehow suppressible:** ~15%. Direct test exists (`test_badge_cannot_be_disabled_via_config`); agent has explicit instruction. Risk lives in JSON serialization paths that don't go through the UI rendering layer.

**Probability of side-pot math bug on the harder cases (fixtures 4, 5):** ~40%. Known correctness pitfall industry-wide.

**Probability of N=2 regression:** ~20%. Strictly-additive contract is achievable but fragile across ~200 LOC of changes to `hunl.py`.

**P(clean READY-no-patches verdict):** ~15%.
**P(READY-with-must-fix verdict):** ~45%.
**P(NOT-READY verdict):** ~30%.
**P(NOT-READY → escalate to PR 12 + PR 12.5 split):** ~10%.

---

## 4. Sequencing + post-audit action

**Trigger:** Audit fires after Wave 2 (B + C) completes (or all three if Pattern A). Per `fanout_ready.md` §6: Wave 1 Agent A (~1.5-3 wk; gate = N=2 regression-clean + fields reconciled) → Wave 2 B+C parallel (~4-9 wk) → full validation battery (pytest 3p + cargo test multiway + full regression + check_pr.sh + string-literal grep) → audit agent (16 focus areas) → resolve must-fix → soak >=1 wk on integration → `--no-ff` merge to main (post-v1 hop).

**Read order:** `audit_prompt.md` → this file → `pr12_spec.md` (§3 theoretical honesty is the spec's reason for existing) → `launch_readiness.md` → `audit_report.md`.

**Post-audit action:**
- <=2 must-fix matching §1 forecast → patch, re-test, commit.
- Must-fix NOT in §1 → blind spots; update this doc for future post-v1 PRs.
- NOT-READY on stability or N=2 regression → escalate; may require PR 12 + PR 12.5 split (per `fanout_ready.md` line 98).
- NOT-READY on framing discipline (badge suppressible, bare "Nash"/"GTO") → MUST-fix immediately; load-bearing deliverable.

**Per memory `feedback_no_extrapolate`:** do NOT claim convergence quality until the integrated stability diagnostic on the river-only fixture confirms it. Agent C's `pr_report.md` must contain `StabilityReport` numbers, not extrapolation from per-component tests.

**Per memory `feedback_continuous_pruning`:** post-PR-12 ship, spawn a prune agent. PR 12 is the largest single doc generator in the roadmap.

---

## 5. Cross-reference checklist for audit launch

- [ ] `git diff main...HEAD` non-empty on `pr-12-three-handed-stretch`.
- [ ] New files exist: `poker_solver/multiway_solver.py`, `crates/cfr_core/src/multiway.rs`, `tests/test_3p_{core,solve,diff}.py`, `tests/fixtures/multiway_fixtures.py`.
- [ ] Modified files exist: `poker_solver/{hunl,action_abstraction,solver,cli,__init__}.py`, `ui/views/{range_matrix,run_panel,library_browser}.py`.
- [ ] `HUNLConfig.num_players` field present; `folded`/`all_in` are N-tuples.
- [ ] `_compute_side_pots` helper exists with all 5 TDA fixture tests.
- [ ] String-literal grep returns ZERO output (per `fanout_ready.md` §5 line 134).
- [ ] `StabilityReport` numbers present in Agent B's or C's `pr_report.md`.
- [ ] Pluribus + Gibson papers exist at `references/papers/`.

If any checkbox unchecked → audit returns NOT READY before any analysis is done.

---

## 6. The honesty deliverable

PR 12's deliverable is **not the solver**. LCFR + 95%-pruning is empirically validated by Pluribus on 6-player; 3-handed is between HUNL and 6-max in difficulty — the solver will converge to *something*.

PR 12's deliverable is the **honesty of the framing**: every output surface labeled "≈ approximate equilibrium" unsuppressibly; every metric labeled per-pair-BR (NOT Nash exploitability); every claim about CFR's properties grounded in what Zinkevich 2007 / Gibson 2013 / Pluribus 2019 actually prove (IDSD elimination + sublinear regret, NOT Nash convergence); every cross-validation harness opt-in (Monker) or structural-only.

PR 3-11 were correctness against a known oracle. PR 12 is "we cannot prove this is right; here is exactly what we know and don't know." **The audit verdict on framing is the audit verdict on PR 12.** If framing slips, the PR does not ship — even if every test passes.
