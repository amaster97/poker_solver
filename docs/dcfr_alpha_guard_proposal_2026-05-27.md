# DCFR α-guard options — proposal (v1.8.1 candidate)

**Task:** #38 — DCFR α=0 silently produces non-Nash strategy
**Date:** 2026-05-27
**Status:** PROPOSAL — awaiting user decision (read-only on code)

---

### Finding

The DCFR solver silently accepts `alpha=0` and returns a non-Nash strategy. At
α=0 the positive-regret discount factor reduces to `t^0 / (t^0 + 1) = 1 / 2`
for every iteration, so accumulated positive regrets are halved every step
regardless of progress — convergence stalls. Reproduction in
`docs/perpetual_qa_findings_2026-05-27.md:1653-1667` (HIGH-1, iter 6 retry):
on Kuhn at 10k iterations α=1.5 hits exploitability ~1.27e-3 while α=0 stays
flat at ~8.6e-2 with game value −0.093 vs the correct ~−0.056 BB (~70%
divergence). The Rust binding (`solve_kuhn`, `solve_leduc`,
`solve_hunl_postflop`, `solve_hunl_preflop`, `solve_range_vs_range_rust`) and
the Python `DCFRSolver` constructor both accept α=0 with no warning or
validation, and `_solve_rust` (`poker_solver/solver.py:652`) defaults α to 1.5
only when the caller omits it — explicit α=0 passes through untouched. The
locked production hyperparameters are (α, β, γ) = (1.5, 0.0, 2.0) per
`docs/a83_validation_2026-05-26.md:42-48` and `crates/cfr_core/src/dcfr.rs:16`,
so this is an out-of-supported-config knob with a known-bad value silently
reachable from every callsite.

---

### Research summary

**Brown & Sandholm 2019 (DCFR paper, `references/papers/dcfr_brown_2019.pdf`)**
is NOT conclusive on α=0. The paper:

- Page 3 (left column, "Regret Discounting for CFR and Its Variants") defines
  the DCFR family `DCFR_{α, β, γ}` and characterizes special cases: LCFR is
  equivalent to DCFR_{1,1,1}, CFR+ to DCFR_{∞,−∞,2}.
- Page 3 (right column): *"In preliminary experiments we found the optimal
  choice of α, β, and γ varied depending on the specific game. However, we
  found that setting α = 3/2, β = 0, and γ = 2 led to performance that was
  consistently stronger than CFR+. Thus, we refer to DCFR with no parameters
  listed, we assume this set of parameters are used."*
- Page 4 (left column, "Experimental setup" preamble): discusses drawbacks of
  β ≤ 0 (regrets approach −∞ for β < 0; constant for β = 0); also analyzes
  β = 0.5 as a pruning-compatible alternative. **α=0 is never mentioned, never
  experimentally validated, and never analyzed.**
- Pages 4–5 (Figures 1–3): experimental curves cover DCFR(1.5, 0, 2),
  DCFR(1.5, 0.5, 2), DCFR(1.5, −∞, 2), CFR, CFR+, LCFR, LCFR+. **No α curve
  with α ≠ 3/2 is shown.**
- The paper's Theorem 2 convergence bound (page 4, right column) is stated
  generically over α, β, γ but the bound's quality is not analyzed at α = 0
  and the experimental support is α = 3/2 only.

**Verdict on Brown:** α=0 is OUT-of-scope of the paper's empirical claims, with
no theoretical statement that it reduces to a known algorithm (it does NOT
reduce to CFR+ — CFR+ is DCFR_{∞, −∞, 2}, not DCFR_{0, …, …}).

**Competitor solvers — what do they allow?**

- `references/code/noambrown_poker_solver/python/src/algorithms/cfr.py:15`
  (Brown's own reference Python solver) — α is a knob:
  `dcfr_alpha: float = 1.5` with no validation. Same accept-and-silently-fail
  surface as our code.
- `references/code/noambrown_poker_solver/cpp/src/trainer.h:16-17` (Brown's
  C++): `struct DcfrParams { double alpha = 1.5; … };` — knob, no
  validation.
- `references/code/postflop-solver/src/solver.rs:11-37` — α is **NOT a knob**.
  `DiscountParams::new(t)` hardcodes `pow_alpha = t_alpha * t_alpha.sqrt()`
  (i.e. `t^1.5`) and `beta_t = 0.5` with no user-facing parameter. The only
  inputs are iteration `t` and game state.
- `references/code/TexasSolver/include/trainable/DiscountedCfrTrainable.h:20`
  — α is **NOT a knob**. `constexpr static float alpha = 1.5f;` at
  compile-time. `src/trainable/DiscountedCfrTrainable.cpp:95-109` uses this
  constant directly.

**Verdict on competitors:** the two production-grade Rust/C++ solvers
(postflop-solver, TexasSolver) treat α as a compile-time constant, not a
runtime knob. Only Brown's reference implementation (which is research code,
not a production solver) leaves α as a configurable parameter, and it shares
our silent-acceptance behavior.

**Locked-hyperparameters spec citations:**

- `docs/a83_validation_2026-05-26.md:35-48` — formal validation that
  (α, β, γ) = (1.5, 0.0, 2.0) match Brown 2019; rated PASS.
- `crates/cfr_core/src/dcfr.rs:16` — module doc: *"Defaults (α, β, γ) =
  (1.5, 0.0, 2.0) — the paper's recommended setting."*
- `poker_solver/dcfr.py:69` — Python `DCFRSolver.__init__` defaults
  `alpha: float = 1.5`.
- `poker_solver/parity/noambrown_wrapper.py:203` — Brown parity wrapper
  hardcodes `_DCFR_ALPHA: float = 1.5`.
- `poker_solver/charts/pushfold_v1.json:29` — packaged chart embeds
  `"alpha": 1.5`.
- The locked-hyperparameter language ("locked DCFR config" in
  `a83_validation_2026-05-26.md:37`) does NOT explicitly forbid runtime
  override; the spec lists 1.5 as the production value but does not declare a
  supported range.

---

### Surface area (where α=0 can be supplied)

Six runtime entry points all accept α as a free `f64` / `float` with no
validation. The Python tier defaults to 1.5; the Rust binding requires α to be
passed positionally so the Python `_solve_rust` wrapper is the only layer that
silently substitutes 1.5 when the caller omits it.

| # | Layer | Entry | File:line | Validation today |
|---|---|---|---|---|
| 1 | Rust PyO3 | `_rust.solve_kuhn` | `crates/cfr_core/src/lib.rs:96-103` | none |
| 2 | Rust PyO3 | `_rust.solve_leduc` | `crates/cfr_core/src/lib.rs:130-139` | none |
| 3 | Rust PyO3 | `_rust.solve_hunl_postflop` | `crates/cfr_core/src/lib.rs:195-208` | none |
| 4 | Rust PyO3 | `_rust.solve_hunl_preflop` | `crates/cfr_core/src/lib.rs:284-294` | none |
| 5 | Rust PyO3 | `_rust.solve_range_vs_range_rust` (vector-form DCFR) | `crates/cfr_core/src/lib.rs:436-447` | none |
| 6 | Rust struct ctor | `DCFRSolver::new` / `DCFRSolver::with_locked` | `crates/cfr_core/src/dcfr.rs:86-107` | none |
| 7 | Rust struct ctor | `PreflopDcfr::new` / `with_locked` | `crates/cfr_core/src/preflop.rs:275-289` | none |
| 8 | Rust struct ctor | `VectorDCFR::new` / `with_init_noise` | `crates/cfr_core/src/dcfr_vector.rs:188-215` | none |
| 9 | Rust struct ctor | HUNL `Solver::new` / `with_locked` | `crates/cfr_core/src/hunl_solver.rs:144-157` | none |
| 10 | Python class | `poker_solver.dcfr.DCFRSolver` | `poker_solver/dcfr.py:65-78` | none |
| 11 | Python entry | `poker_solver.solver._solve_rust` | `poker_solver/solver.py:652` | none (only defaults missing keys to 1.5) |
| 12 | Python entry | `poker_solver.range_aggregator.solve_range_vs_range` | `poker_solver/range_aggregator.py:884` | none |

**CLI surface:** `poker_solver/cli.py` (the `solve` subcommand starting at
line 1101) does **NOT** expose `--alpha` / `--beta` / `--gamma`. The
`poker_solver/hunl_solver.py:21` docstring describes them as reserved CLI
flags but no `add_argument` registers them. The only `--dcfr-alpha` flag in
the repo is `poker_solver/parity/noambrown_wrapper.py:696` — this targets the
Brown reference C++ binary, not our solver. So **end-user CLI cannot reach
α=0 today**; the surface is library / Python-API only.

**Net surface:** 9 Rust entry points (4 PyO3 functions + 4 struct constructors
+ 1 HUNL solver) and 3 Python entry points. A guard in
`DCFRSolver::with_locked` (and its sibling constructors) is the smallest
change that covers all of them, because every PyO3 entry funnels into a
constructor.

---

### Options

Each option includes an actual diff fragment against the current code, not
pseudocode. All three are read-only proposals — the user picks before any
code lands.

#### Option A — HARD-FAIL on α ∉ {1.5}

**Approach.** Reject any α other than the production-locked value. Strictest.
Removes α as a knob entirely.

**Diff fragment** (in `crates/cfr_core/src/dcfr.rs`, around line 91):

```rust
     /// Construct a solver with a pre-populated lock map (v1.4 node-locking).
     pub fn with_locked(
         alpha: f64,
         beta: f64,
         gamma: f64,
         locked_strategies: HashMap<String, Vec<f64>>,
     ) -> Self {
+        // v1.8.1: HARD-FAIL on out-of-spec α. The locked production
+        // hyperparameter is α=1.5 (Brown & Sandholm 2019, recommended;
+        // docs/a83_validation_2026-05-26.md). α=0 silently produces
+        // non-Nash strategies (positive regrets halved every iter); no
+        // other α value has been validated against the paper's
+        // experimental support.
+        if (alpha - 1.5).abs() > 1e-9 {
+            panic!(
+                "DCFR α must be 1.5 (locked production value); got {alpha}. \
+                 Other values are out-of-spec and may produce non-Nash \
+                 strategies (e.g. α=0 stalls convergence). If you need to \
+                 experiment, edit DCFR_ALPHA_LOCKED and rebuild."
+            );
+        }
         Self {
             alpha,
             ...
```

Mirror the same panic in `preflop.rs:280`, `dcfr_vector.rs:207`,
`hunl_solver.rs:149`. Add a corresponding `raise ValueError` in
`poker_solver/dcfr.py:78` and `poker_solver/solver.py:652`. PyO3 panics
already get caught and surfaced as `PyValueError` by the existing
`catch_unwind` wrappers (`lib.rs:109`, `:225`, etc.), so the Rust panic
becomes a Python exception at the binding boundary.

**Pros.** Zero silent-bug surface; aligns the API to the production-locked
value the test suite actually validates; matches the
`postflop-solver` / `TexasSolver` design (α as compile-time constant).

**Cons.** Removes the experimentation knob entirely. If a user has a
legitimate reason to try α=2.0 or α=1.0 (e.g. paper-reproduction of
DCFR_{1,1,1} = LCFR per the paper page 3), they can't without editing source.
Differential-test infrastructure that varies α to probe the solver (e.g.
`docs/perpetual_qa_findings_2026-05-27.md:337` — `solve_kuhn(..., alpha=2.0)`)
breaks.

---

#### Option B — WARN on α < 0.5, HARD-FAIL on α ≤ 0

**Approach.** Allow a band of experimentation consistent with the paper's
qualitative analysis (α as a positive exponent on `t^α`), but block the
known-broken α=0 endpoint and warn on the suspicious-low band where the
discount factor at t=1 is ≤ 0.59 (i.e. `1^0.5/(1^0.5 + 1) = 0.5` at α=0.5,
trending to 0.5 as α→0).

**Diff fragment** (in `crates/cfr_core/src/dcfr.rs`, around line 91):

```rust
     pub fn with_locked(
         alpha: f64,
         beta: f64,
         gamma: f64,
         locked_strategies: HashMap<String, Vec<f64>>,
     ) -> Self {
+        // v1.8.1: validate α range. α ≤ 0 is rejected (degenerate:
+        // positive regrets halved every iter regardless of progress;
+        // Kuhn fixture stays at exploitability 8.6e-2 vs 1.27e-3 at
+        // α=1.5 — see docs/perpetual_qa_findings_2026-05-27.md HIGH-1).
+        // α < 0.5 warns (Brown & Sandholm 2019 §"Regret Discounting"
+        // analyzes α = 3/2 only; no experimental support below ~1.0).
+        if !alpha.is_finite() || alpha <= 0.0 {
+            panic!(
+                "DCFR α must be > 0 and finite; got {alpha}. α=0 silently \
+                 stalls convergence (positive regrets halved every iter); \
+                 α<0 has no theoretical or empirical support."
+            );
+        }
+        if alpha < 0.5 {
+            eprintln!(
+                "[dcfr] WARNING: α={alpha} is below the paper's analyzed \
+                 range (Brown 2019 validates α=3/2 only; convergence \
+                 below α≈1.0 is empirically much slower). Locked \
+                 production value is α=1.5."
+            );
+        }
         Self {
             alpha,
             ...
```

Same mirror in `preflop.rs`, `dcfr_vector.rs`, `hunl_solver.rs`. Python tier
uses `raise ValueError` for the hard-fail and `warnings.warn(..., DeprecationWarning)`
for the soft warning.

**Pros.** Blocks the known-broken α=0 case; preserves the differential-test /
paper-reproduction knob; matches Brown's qualitative paper guidance (α > 0).
Lowest behavioral disruption for legitimate callers.

**Cons.** The 0.5 threshold is an authored judgment, not paper-derived
(Brown doesn't characterize a "supported lower bound"). Warnings printed to
stderr can be missed in noisy environments. Two failure modes (warn vs panic)
is more API surface than one.

---

#### Option C — Document only, no code change

**Approach.** Add explicit prose to `crates/cfr_core/src/dcfr.rs:16-17`,
`poker_solver/dcfr.py:46-48`, and the README, stating α=0 produces non-Nash
strategies and the only validated value is α=1.5. No runtime guard.

**Diff fragment** (in `crates/cfr_core/src/dcfr.rs`, around line 16):

```rust
 //! Defaults (α, β, γ) = (1.5, 0.0, 2.0) — the paper's recommended setting.
+//!
+//! ## α range (CRITICAL)
+//!
+//! Only α = 1.5 has been empirically validated against the paper's
+//! experimental support (Brown & Sandholm 2019 §"Regret Discounting"). In
+//! particular, **α = 0 silently produces a non-Nash strategy**: the
+//! positive-regret discount reduces to `t^0 / (t^0 + 1) = 0.5` for every
+//! iteration, halving accumulated positive regrets every step regardless
+//! of progress. On Kuhn at 10k iter, α=0 stalls at exploitability ~8.6e-2
+//! vs ~1.27e-3 at α=1.5 (docs/perpetual_qa_findings_2026-05-27.md HIGH-1).
+//! The constructor does NOT validate α; callers are responsible for
+//! passing only the locked production value (1.5).
```

Mirror the same caveat in `poker_solver/dcfr.py:46-48` (alpha docstring) and
add a one-line "Hyperparameter guard" section to README.md.

**Pros.** Zero behavioral change; no risk of breaking existing differential
tests / experiments; smallest possible diff (docs only).

**Cons.** Leaves the silent-failure surface entirely intact. Users who don't
read the docstring (including future Claude sessions running smoke tests) can
still type `alpha=0` and get a bad strategy with no signal at runtime.
Documentation is not enforced.

---

### Recommendation

**Pick Option B.** Rationale:

1. **Blocks the known-broken case.** α=0 is the specific failure mode the QA
   reproduction catches; a hard-fail on α ≤ 0 closes it.
2. **Preserves the existing surface where it matters.** The repo already has
   working test code that calls `solve_kuhn(..., alpha=2.0)` for sensitivity
   probes (`docs/perpetual_qa_findings_2026-05-27.md:337`,
   `docs/perpetual_qa_findings_2026-05-27.md:2072`). Option A would break
   these and force every differential test to thread through a fresh
   `DCFR_ALPHA_LOCKED` override path.
3. **Matches the paper's qualitative shape.** Brown's analysis treats α as a
   positive exponent on `t^α`; α ≤ 0 has no paper support whatsoever, so a
   hard-fail there is paper-consistent rather than over-restrictive.
4. **Warning band catches the "I saw α=1.5 and wondered if smaller is faster"
   intuition** (which is what produced the iter 6 retry HIGH-1) without
   blocking it.
5. **Option C alone is insufficient.** The reproduction in QA iter 6 retry
   was performed by someone (or a smoke-test agent) following the
   reasonable intuition that "α=0 = no positive-regret discount = vanilla
   CFR." Docs don't enforce that intuition fails; runtime validation does.
6. **Option A is correct but overkill given the test surface.** If the user
   has no current need to vary α and wants the hardest guarantee, A is
   strictly safer than B — but only marginally, because B's hard-fail at α≤0
   covers the only empirically-broken case.

The tightest reasonable bound the paper supports is "α > 0". B's soft-warn
threshold at α < 0.5 is a judgment call; an alternative is to drop the warn
band and only hard-fail on α ≤ 0, but that loses the affordance for
"hey, you're outside the validated range."

If the user wants strictness (A) over experimentation, Option A is
implementable from this same diff sketch by tightening the hard-fail
condition from `alpha <= 0.0` to `(alpha - 1.5).abs() > 1e-9`.

---

### Test plan

Same suite covers all three options; the only difference is which assertions
fire.

**Existing tests to re-run (regression).**

- `cargo test -p cfr_core` — the existing Kuhn / Leduc / HUNL differential
  tests run at α=1.5 and must still pass under any option.
- `pytest tests/test_dcfr_diff.py` — Python ↔ Rust differential at α=1.5;
  unchanged.
- `pytest tests/test_solve_kuhn_rust.py` (and similar Rust-binding smokes) —
  must still accept α=1.5 silently.

**New unit tests (one per affected layer).**

For **Option A**:
- `test_dcfr_rejects_alpha_2_0` — assert `DCFRSolver::new(2.0, 0.0, 2.0)`
  panics with the expected message.
- `test_pyo3_solve_kuhn_rejects_alpha_2_0` — assert
  `_rust.solve_kuhn(100, 2.0, 0.0, 2.0)` raises `PyValueError`.
- `test_python_dcfr_rejects_alpha_2_0` — assert
  `DCFRSolver(game, alpha=2.0)` raises `ValueError`.
- Update `test_alpha_sensitivity_smoke` (if any) to skip on Option A.

For **Option B**:
- `test_dcfr_rejects_alpha_zero` — assert `DCFRSolver::new(0.0, 0.0, 2.0)`
  panics.
- `test_dcfr_rejects_alpha_negative` — assert `DCFRSolver::new(-0.5, …)`
  panics.
- `test_dcfr_rejects_alpha_nan` — assert `DCFRSolver::new(f64::NAN, …)`
  panics (caught by `!alpha.is_finite()`).
- `test_dcfr_warns_alpha_below_half` — capture stderr / use Python
  `warnings.catch_warnings()` and assert a warning is emitted for α=0.3.
- `test_dcfr_accepts_alpha_2_0_silently` — α=2.0 should construct without
  panic or warn.
- `test_pyo3_solve_kuhn_rejects_alpha_zero` — `PyValueError` from the
  binding.

For **Option C**:
- No runtime tests. Add a `tests/test_docs_dcfr_alpha_note.rs` (or a `pytest`
  doctest) that asserts the README and module-level rustdoc contain the
  substring "α = 0" / "non-Nash" so the warning isn't silently deleted.

**Verification — does the bug actually trigger and the fix actually fix?**

Reproduce the QA iter 6 retry fixture:

1. `pytest tests/test_kuhn_dcfr.py::test_alpha_zero_repro` (new) — assert
   the existing solver at α=0 hits exploitability > 1e-2 at 10k iter (i.e.
   confirm the bug is real on this machine).
2. Add the guard per the chosen option.
3. Re-run the same test, expecting `ValueError` / `PyValueError` instead of
   a returned bad-strategy result. The "guard catches the broken case" is
   the load-bearing claim.

**Empirical-over-audit checkpoint.** Per the project's
`feedback_empirical_over_audit` rule: do NOT mark the fix shipped on a code
audit alone. The repro test in step 1+3 above is the empirical signal — it
must fail (the bug) before the guard, and raise (the guard) after. If only
step 3 is run and it passes, that proves nothing.

---

### What this PR ships

This PR contains **only this proposal document**. No code changes. The user
picks A, B, or C; a follow-up PR (v1.8.1 if greenlit) implements the chosen
option per the diff sketch and test plan above.
