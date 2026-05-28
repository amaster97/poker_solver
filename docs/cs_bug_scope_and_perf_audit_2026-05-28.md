# cs-Bug Scope Audit + Perf Claim Re-Validation (2026-05-28)

Context — PR #159 documents a bug in `PreflopRvrState::initial`
(`crates/cfr_core/src/preflop_rvr.rs:229-251`) that unconditionally
overwrites `contributions = [SB+ante, BB+ante]` from blinds, ignoring
`config.initial_contributions`. Downstream leaves compute
`cs = contributions - initial_contributions`. If a caller passes
`initial_contributions = [SB, BB]` (intending to declare posted
blinds), `cs` zeroes out → `pot_total = initial_pot + cs0 + cs1 = 0` at
every leaf → fold dominates → degenerate Nash.

This audit determines:
  A) whether the same pattern is reachable in other subgame solvers
     (postflop / river / turn / chained); and
  B) whether shipped perf claims (#114 / #139 / #150 / #157) were
     measured on the affected path or on a sound path.

All citations are absolute file:line in the worktree at
`/Users/ashen/Desktop/poker_solver_worktrees/audit-cs-bug-scope`.

---

## Section A — Bug-scope table

| Entry point | State::initial path | Uses `config.initial_contributions` correctly? | Leaf math uses `cs = contributions - initial_contributions`? | Same bug present? | Severity (preconditions to trigger) |
|---|---|---|---|---|---|
| `solve_hunl_preflop_rvr(_with_hands)` (`crates/cfr_core/src/preflop_rvr.rs:1388, 1417`) | `PreflopRvrState::initial` (`crates/cfr_core/src/preflop_rvr.rs:229-251`) | **NO** — hardcodes `[sb_contrib, bb_contrib]` at line 238, ignores `config.initial_contributions` | YES — `build_equity_leaf_payoff` line 643-645, fold-leaf line 767-769, `update_node_leaf` line 1291-1292 | **YES** | Bug triggers iff caller passes `initial_contributions != [0,0]` AND `starting_street == Preflop`. Python `HUNLConfig.__post_init__` (`poker_solver/hunl.py:146-148`) BLOCKS this combination. Reachable only via Rust-direct callers (Rust tests, FFI bypass). |
| `solve_hunl_preflop` (`crates/cfr_core/src/preflop.rs:493`) | `HUNLState::initial_preflop` (`crates/cfr_core/src/hunl.rs:382-414`) | **NO** — line 385: `let contributions = [sb_contrib, bb_contrib];` mirrors the preflop_rvr bug | YES — `HUNLState::utility` lines 499-504 use `cs = contributions - initial_contributions` | **YES** | Same precondition as preflop_rvr; Python guard also applies. Additionally, `preflop_subgame_utility` in `crates/cfr_core/src/preflop.rs:241-254` uses a different leaf formula `risk = min(c0, c1); pot = 2*risk` that ignores both `initial_pot` AND `initial_contributions` — separate concern, but masked by the [0,0] Python guard. |
| `solve_hunl_postflop` (`crates/cfr_core/src/hunl_solver.rs:477`) | `HUNLState::initial` postflop branch (`crates/cfr_core/src/hunl.rs:318`) | **YES** — line 318: `let contributions = config.initial_contributions;` correctly | YES — same `state.utility()` path | **NO** | Postflop path correctly wires `initial_contributions` through. Asymmetric `[c0, c1]` configs (e.g. facing-bet flop subgames) handled at lines 330-348. Sound. |
| `solve_range_vs_range_postflop(_with_hands)` (`crates/cfr_core/src/dcfr_vector.rs:1226, 1259`) | `HUNLState::initial` postflop branch (via line 1285) | **YES** — same correct postflop branch | YES — `TerminalCache::build` lines 154-156 (Fold) and 174-176 (Showdown) | **NO** | Sound. |
| Python `solve_chained` (`poker_solver/chained.py:376`) | Dispatches per street to Rust preflop / postflop entry points | Inherits Python validation | n/a | **NO at composition** | Chained is preflop-then-postflop. Preflop leg requires `[0,0]` (Python guard). Postflop leg gets `[c0, c1]` reflecting preflop outcome. Composition is sound because the broken-preflop entry is unreachable via Python. |

**Verdict: PARTIAL.** The same buggy `State::initial` pattern exists in
TWO solvers (`preflop_rvr` AND `preflop`), but in production the
Python layer blocks the only config combination that would trigger
either. The bug is reachable from:
  - Rust-direct integration tests that construct a `HUNLConfig` with
    `starting_street == Preflop` AND `initial_contributions != [0,0]`
    (bypassing `__post_init__`)
  - Future Rust-only or non-Python callers
  - Refactors that relax the Python guard

Postflop solvers (`solve_hunl_postflop`, `solve_range_vs_range_*`,
`exploit.rs` BR-walk) are NOT affected. They use the correct postflop
branch at `crates/cfr_core/src/hunl.rs:318`.

---

## Section B — Perf-claim table

| Perf claim | Source | Benchmark file | Bench config — `starting_street` | Bench config — `initial_contributions` | Hits buggy path? | Verdict |
|---|---|---|---|---|---|---|
| PR #157 — `6.5× wall speedup, 10.3× kernel speedup` on full-tree preflop RvR | GitHub PR #157 body | `crates/cfr_core/benches/preflop_rvr_profile.rs:42-66` | `Preflop` (line 50) | `[0, 0]` (line 51) | **NO** — `[0,0]` is the trivial subtraction case; `cs == contributions`, leaf math degrades to the same arithmetic regardless of the bug | **STANDS.** Bench measured the optimization on a sound config. The opp-major layout + AXPY interchange yields 6.5× independent of contribution-anchor logic. |
| PR #114 — `213× river RvR speedup` via TerminalCache | GitHub PR #114 body | `crates/cfr_core/benches/rvr_profile.rs:33-100` | `River` (lines 50, 83) | `[500, 500]` (lines 53, 86) | **NO** — postflop path (`crates/cfr_core/src/hunl.rs:318`) correctly wires `initial_contributions`; `cs = [500-500, 500-500] = [0,0]` AS INTENDED, plus `initial_pot=1000` contributes correctly | **STANDS.** Postflop solver is not affected by the cs bug. |
| PR #139 — BR-walk caching | GitHub PR #139 body | Same `rvr_profile.rs` + `crates/cfr_core/src/exploit.rs:1415, 1529, 1609` (Rust unit tests `initial_contributions: [500, 500]`) | River / postflop | `[500, 500]` | **NO** — postflop path | **STANDS.** |
| PR #150 — board-isomorphism cache | GitHub PR #150 body | Python-side (`tests/test_chained_orchestrator_cache.py`); no engine math change | Postflop iso-equivalence | n/a (cache key only) | **NO** — additive Python wrapper, no engine touch | **STANDS.** |
| Python `tests/test_preflop_rvr_diff.py` differential test | `tests/test_preflop_rvr_diff.py:162, 244` | n/a (test, not bench) | `Preflop` via `HUNLConfig(starting_stack=...)` | `[0, 0]` (defaults; `(300, 300)` at line 313 is a RIVER fixture, not preflop) | **NO** — `[0,0]` is the safe value | **NOT VACUOUSLY PASSING.** Tests compare Rust output against chart-jam / chart-fold heuristics (not against a Python preflop_rvr engine, which doesn't exist). |
| Iter-count vs wall-time tables | (no docs hit on grep `iters` + `wall` for preflop_rvr) | n/a | n/a | n/a | n/a | **N/A** — no such tables shipped that size iter-counts off degenerate-fast wall. |

**Verdict (perf claims): ALL STAND.** Every benchmark either uses
`initial_contributions = [0, 0]` (preflop_rvr_profile — degenerate
subtraction yields the same result regardless of bug) or uses the
postflop path that is NOT affected by the bug. No published perf
number is invalidated.

---

## Section C — Recommendation, prioritized by user impact

**1. Fix `PreflopRvrState::initial` and `HUNLState::initial_preflop` to
   honor `config.initial_contributions` (HIGHEST PRIORITY).**

The bug is latent today but is a footgun for:
  - any Rust-direct integration test that mirrors a real subgame
  - any future feature that wants to solve a preflop subgame starting
    from a non-default chip state (e.g. tournament ICM-aware preflop,
    re-entry preflop with leftover dead money, exploitative deviations
    that start mid-preflop after a known opponent action)
  - any FFI consumer that bypasses the Python `__post_init__` guard

Fix shape (do NOT auto-apply per task constraints):

  - `crates/cfr_core/src/preflop_rvr.rs:229-251` — replace
    `contributions: [sb_contrib, bb_contrib]` with
    `contributions: [config.initial_contributions[0] + sb_contrib,
                     config.initial_contributions[1] + bb_contrib]`
    OR refactor so `initial_contributions == [SB, BB]` is the explicit
    contract and the function reads contributions from the config.
    Resolve the convention question first (does
    `initial_contributions` mean "chips already in pot pre-blinds" or
    "total committed including blinds"?).
  - `crates/cfr_core/src/hunl.rs:382-414` — apply the same fix to the
    HUNL preflop branch. Currently divergent from the postflop branch
    at line 318, which DOES use `config.initial_contributions`.

**2. Add a Rust-side `HUNLConfig::validate()` that mirrors Python's
   `__post_init__` (MEDIUM PRIORITY).**

Today the only guard against the buggy config combination is in
Python. Rust integration tests, Rust-only consumers, and any future
non-Python caller can construct an invalid config silently. A Rust
`validate()` would HARD-FAIL at config construction, matching the
[Silent no-op hazard](feedback_silent_noop_hazard.md) rule in
project memory.

**3. Add a Rust unit test that exercises preflop with
   `initial_contributions = [SB, BB]` (LOW PRIORITY, blocked on #1).**

After the fix in #1 lands, add a test that constructs the same config
PR #159 documents and asserts `pot_total > 0` at the first leaf. This
would be a regression smoke for the bug class.

**4. No perf-claim retraction required.** All published numbers stand;
   the bug never had the opportunity to skew them because every
   benchmark either used the trivial `[0,0]` case or the unaffected
   postflop solver. No `RELEASE_NOTES_*` or `docs/perf_*` text needs
   amendment based on this audit.

---

## Notes / process

- This audit is read-only. No engine code modified.
- The audit was driven by file:line grep over
  `crates/cfr_core/src/*.rs` for `initial_contributions` and by
  cross-checking each State::initial dispatch against its
  corresponding leaf-utility formula.
- The Python guard at `poker_solver/hunl.py:146-148` is the single
  load-bearing safeguard preventing the bug from reaching production
  paths today. Removing it without fixing the Rust side would
  re-expose the degenerate-Nash failure mode.
