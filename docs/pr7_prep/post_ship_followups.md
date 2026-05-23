# PR 7 post-ship follow-ups

**Status:** PR 7 shipped at `83d7b9c` (branch `pr-7-noambrown-diff`).
**Scope of this doc:** track items intentionally deferred at ship time so a future cleanup PR (suggested: **PR 7.5**) can land them without re-litigating PR 7's audit.
**Source of truth for findings:** `docs/pr7_prep/audit_report.md` (M1/M2/M3 patched pre-ship; S1–S8 + N1–N6 deferred).

---

## 1. Audit findings deferred (7 should-fix items)

The PR 7 audit (`audit_report.md`) flagged 8 should-fix items. **S5** was confirmed-correct on inspection (the `set -e` + `find | grep -q` interaction is safe inside an `if` condition); the remaining seven were deferred to keep the PR scoped to the M1/M2/M3 blockers and the spec'd parity infrastructure. Re-attack list:

- **S1. Test filenames diverge from spec.** Rename `tests/test_river_diff.py` → `tests/test_noambrown_river_parity.py` and `tests/test_river_diff_self_sanity.py` → `tests/test_noambrown_self_sanity.py` per spec §7. Internal docstrings already point to the new names; this is a pure rename + grep-sweep for stale references in PR 10a / PR 11 docs.
- **S2. `run_brown_solver` uses `tempfile.mkdtemp` instead of `NamedTemporaryFile`.** Either add an inline comment at `poker_solver/parity/noambrown_wrapper.py:574` justifying the deviation, or switch to literal `NamedTemporaryFile(suffix=".json", delete=False)` compliance. Functionally equivalent; cosmetic spec-fidelity.
- **S3. `SMOKE_SEED = 42` vs harness `BROWN_SEED = 7`.** Align `SMOKE_SEED` in the self-sanity smoke test to 7 so the determinism smoke exercises the same RNG state as Agent B's diff. Spec §11 #1 paranoia.
- **S4. `iterations_run` is vacuously equal to `iters`.** Parse Brown's stdout `"Discounted CFR: iters=N"` marker into `BrownStrategyDump.iterations_run` (add `_ITERS_RE` alongside the existing `_EXPL_RE` in `noambrown_wrapper.py`) so the harness's `assert brown_dump.iterations_run == iters` is non-trivially true.
- **S5 (caveat to "looks good").** Wrap `cmake --build "$BUILD" -j` in `scripts/build_noambrown.sh` with an explicit `if ! ... ; then echo "compile failed (likely missing Xcode CLT or stdlib header)"; exit 0; fi` so Xcode-CLT-missing hosts soft-fail at compile time, not at toolchain-lookup time. Was logged under "Looks good" §1 with a caveat — still worth the polish.
- **S6. Self-sanity vs Agent B smoke-test overlap.** Now that M1 has been remediated (the spec'd 8 binary-independent tests live in `test_river_diff_self_sanity.py`), the original 4 binary-required smoke tests need a home. Either fold them into the Agent B module under `parity_noambrown`, or move them to `tests/test_river_diff_brown_smoke.py`. Audit M1 fix may have already done this — verify before reopening.
- **S7. `our_strategy_to_brown_matrix` silently drops unrecognized infoset keys.** Add a `warnings.warn(...)` (or opt-in `strict=True` kwarg) so silent coverage loss surfaces upstream of the 80% gate.
- **S8. `iterations_override` upper-bound validation missing.** Add a 200_000 cap on `iterations_override` in the `RiverSpot` constructor / loader so a typo'd `10**9` is rejected at load time rather than at `subprocess.TimeoutExpired` three hours into CI.

Nice-to-fix items N1–N6 (cosmetic; see audit §Nice-to-fix) are lower priority and can be batched into the same sweep or skipped.

---

## 2. Latent runtime concern: test_river_diff.py × Brown binary @ 2000 iters

`tests/test_river_diff.py` (15 spots × 2000 iters via Brown + 2000 iters via our solver, both walked to expl < 0.02 × pot) **runs slow when the Brown binary is built**: empirically ~10+ min for the full sweep on an M-series machine, possibly more on CI. This is acceptable behavior for an opt-in `parity_noambrown`-marked suite but is a foot-gun for any future contributor who runs `pytest` without filtering by marker.

The 5-layer skipif strategy keeps the suite **collection-fast and run-fast when the binary is absent** (which is the default on dev machines and CI). The runtime concern is only realized when (a) `bash scripts/build_noambrown.sh` succeeds AND (b) the runner does not filter out `parity_noambrown`.

**Mitigations to consider in PR 7.5:**
- Add `@pytest.mark.slow` **in addition to** `@pytest.mark.parity_noambrown` on the per-spot diff test. The two markers are non-overlapping in intent: `parity_noambrown` gates on opt-in, `slow` gates on duration. Both should fire.
- Document the runtime expectation in `tests/test_river_diff.py`'s module docstring (currently lines 25-38 cover skipif strategy but not runtime).
- Consider a `--brown-quick` opt-in to drop to 200 iters for smoke-grade parity (would loosen tolerance to ~5%; useful for PR-level CI but not for the 5e-3 gate).

---

## 3. Scope creep that needs reversion (handled, but tracked)

**Context.** Between PR 7's commit at `83d7b9c` and PR 10a's commit, a `@pytest.mark.slow` decorator was added to one or more PR 7 tests **as part of PR 10a's diff**. This was scope creep: PR 10a's purpose is the `slow`/`very_slow` marker rollout across the **existing** test suite (PR 1–6 tests + the brand-new PR 7 suite), but the rollout should land in **PR 7.5 (or PR 4.5b)** alongside the rest of the deferred audit items, **not** in PR 10a.

**Status.** Reverted (just). The `@pytest.mark.slow` additions on PR 7 tests are no longer in PR 10a's diff. PR 10a is back to its original scope (timeout/marker discipline on the pre-PR-7 test suite + the `parity_noambrown` marker registration).

**Action item for PR 7.5:** redo the marker addition properly — see §4 below.

---

## 4. Suggested scope for PR 7.5 (or PR 4.5b sweep)

A tight follow-up PR that bundles deferred audit polish + the marker rollout that doesn't belong in PR 10a:

1. **`@pytest.mark.slow` on genuinely-slow PR 7 tests, properly scoped.**
   - The per-spot `test_river_parity_vs_brown` body is the slow path (2000 iters × 2 engines × 15 spots).
   - The Agent C `test_each_spot_solver_converges` is also slow (2000 iters × 15 spots × our solver only).
   - The binary-smoke tests (`test_brown_binary_*`) are fast — do NOT mark.
   - The canonicalization round-trip + matrix-shape + finder tests are fast — do NOT mark.
   - Mark both slow tests with **dual decorators**: `@pytest.mark.parity_noambrown` + `@pytest.mark.slow`. Justification: opt-in gating and duration gating are orthogonal.

2. **Fix `solve_river_subgame_explicit_ranges` helper for per-hand iteration.**
   - The current helper (see `poker_solver/solver.py` — verify path during PR 7.5 prep) does not cleanly support per-hand iteration counts when the caller wants to converge each river spot independently. The Agent C `test_each_spot_solver_converges` works around this by calling the top-level solver in a loop, which is wasteful.
   - The right fix is a `iterations_per_spot: dict[str, int] | None` kwarg on the helper, falling through to a default. Spec §5 step 2 anticipates per-spot overrides via `RiverSpot.iterations_override`; the helper should respect them.

3. **Audit should-fix S1–S8** (minus S5 which was just confirmed-safe).

4. **Audit nice-to-fix N1–N6** if time permits.

5. **Documentation cleanup.** The PR 7 prep directory under `docs/pr7_prep/` has ~20 files of working notes (prompts, audit drafts, commit plans). After PR 7.5 ships, archive or delete the bulk of them per the continuous-pruning rule; keep only `audit_report.md`, `pr7_spec.md`, and this `post_ship_followups.md` as the durable record.

**Recommended PR scope:** items 1–3. Items 4–5 are bonus.

**Effort estimate:** ~1 day of agent work; small, contained, no cross-cutting changes. Can run in parallel with PR 8 (next major) if branches are kept disjoint.

**Branch name (suggested):** `pr-7p5-audit-followups`.

---

## 5. Out-of-scope explicitly

- **No re-opening of M1/M2/M3.** Those landed in `83d7b9c` and are sealed.
- **No changes to PR 10a.** PR 10a stays focused on its original scope (timeout discipline on pre-PR-7 tests + marker registration). The PR 7 marker additions belong in PR 7.5.
- **No changes to the parity_noambrown marker semantics.** `pyproject.toml:42` is canonical.
- **No license / attribution changes.** Audit §License compliance verified clean.
