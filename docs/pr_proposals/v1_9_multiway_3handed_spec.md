# v1.9 (or v2.0) — 3-Handed Multiway HUNL Port from slumbot2019

**Status:** DRAFT spec. Not scheduled. Candidate for v1.9 (or v2.0).
**Date drafted:** 2026-05-25
**Source upstream:** Eric Jackson, `slumbot2019` (MIT). Local path: `references/code/slumbot2019/`.

---

## 1. Executive summary (plain English)

Today we solve heads-up (2-player) postflop spots. **Multiway** — 3+ players still in the hand — is the single biggest scenario class we don't cover. Per the OSS competitor review (`docs/oss_competitor_comparison_2026-05-23.md`), shipping 3-handed postflop would let us claim *"the only free GUI-driven multiway postflop solver."* PioSolver does not offer it; GTO Wizard's 3-handed library is thin and locked behind subscription.

The work is **non-trivial**: CFR has no convergence guarantee with 3+ players, the betting tree must understand side pots and N-way action, and our vector-form engine assumes exactly two reach-probability vectors. We propose porting Eric Jackson's MIT-licensed `mp_ecfr` (multiplayer external-sampling CFR) and `mp_betting_tree` as the structural skeleton, then re-skinning to our DCFR + range/vector form.

**Recommendation:** schedule **after** v1.7.1 ships and v1.8 SIMD lands. Tag as **v1.9** if scope holds; promote to **v2.0** if early prototyping reveals the abstraction rewrite touches the public Python API.

---

## 2. Goal

3-handed NLHE postflop solving (SB + BB + UTG/Button) using the existing DCFR vector-form engine, extended to N=3 players. Output is an **approximate** equilibrium (CFR is not guaranteed to converge for ≥3 players; we report exploitability bounds, not Nash certificates).

Non-goal: prove convergence. We document the no-guarantee caveat in the GUI and in `USAGE.md`.

---

## 3. Why 3-handed (and not 4+)

- **3-handed is by far the most common multiway scenario** beyond HU: SNG finals, 3-bet pots with one caller, button-vs-blinds 3-way after a flat.
- **PioSolver doesn't offer it.** Their engine is HU-only.
- **GTO Wizard** offers limited 3-handed preflop solutions, but no flexible 3-handed postflop solver — and it's subscription-gated.
- **Headline differentiator.** We're already PioSolver-class at HU (per v1.7 parity audit). Multiway is the one feature claim no competitor matches.
- **4+ player is out of reach** on consumer hardware: tree size explodes geometrically with player count; production multiway research (Pluribus) used cluster compute. We draw the line at 3.

---

## 4. Architecture

Extends current `HUNLPoker` engine to N players, parameterized by player count.

**Module-level changes:**

| Layer | Change | Risk |
|---|---|---|
| `HUNLConfig` → `MultiwayConfig` | Add `num_players: int` field (default 2 for backcompat) | LOW |
| `BettingTree` builder | Rewrite to track `folded[N]`, `active[N]`, `contributions[N]`, `next_player_to_act` rotation | **HIGH** |
| `TerminalNode` payoff | N-way side-pot resolution at showdown (port `SetShowdownPots`) | MEDIUM |
| DCFR traversal | Loop `for p in range(N): traverse_for_player(p)` instead of `traverse(0); traverse(1)` | LOW |
| Range / reach-probs storage | N reach-probability vectors instead of 2 | MEDIUM |
| Showdown evaluator | N-way hand comparison + tie/chop handling | LOW (logic) / MEDIUM (perf) |
| CLI surface | Accept `--num-players 3`, validate; route 2-player path unchanged | LOW |
| GUI surface | New 3-handed setup screen, range/stack/position triple-pickers | MEDIUM |

**Architectural invariant:** N=2 path stays bit-identical to current behavior. We branch only when `num_players > 2`.

---

## 5. What we port from slumbot2019

Read-through completed 2026-05-25. Relevant files in `references/code/slumbot2019/src/`:

| File | LOC | What it gives us |
|---|---|---|
| `mp_ecfr.h` / `mp_ecfr.cpp` | ~620 | Multiplayer external-sampling CFR loop. `Process(node)` does target-player update; opponent nodes sample one action. |
| `mp_ecfr_node.h` / `mp_ecfr_node.cpp` | ~210 | Node struct with `player_acting`, `player_remaining`, terminal/showdown flags, regrets/sumprobs arrays per-bucket × succs. Includes `SetShowdownPots` for side-pot construction. |
| `mp_betting_tree.cpp` | ~450 | **Reentrant** N-player betting tree builder. Key functions: `CreateMPFoldSucc`, `CreateMPCallSucc`, `CreateMPHandleBet`, `CreateMPSuccs`. Handles `num_players_to_act` countdown, next-player rotation around folded seats, big-blind-can't-open-fold preflop rule. |
| `mp_vcfr.cpp` / `mp_vcfr.h` | ~910 | Vector-form multiplayer CFR (closer to our engine model). Probably the better long-term port target. |

**Style note from the upstream:** node construction uses mutable arrays (`folded[]`, `active[]`, `contributions[]`, `stack_sizes[]`) passed down + restored after each subtree — a stateful DFS. We'll wrap this in Python/Rust with the same in-place mutation pattern for cache locality.

---

## 6. License consideration

slumbot2019 is **MIT** (Copyright (c) 2019 Eric Jackson). Verbatim porting is permitted with:

1. MIT notice + copyright preserved in any verbatim file (e.g., the betting-tree builder).
2. CHANGELOG entry for v1.9 crediting Eric Jackson and linking to upstream.
3. Inline comment block at the top of every ported file: *"Adapted from slumbot2019 (MIT), Eric Jackson, 2019."*
4. A `THIRD_PARTY_NOTICES.md` file (or section in existing one) listing slumbot2019 alongside any other third-party.

Our DCFR adaptation layer is original work and stays under our existing license.

---

## 7. Scope boundaries

**In scope (v1.9):**

- 3-handed postflop solves on **river** and **turn** fixtures.
- Equal starting stacks (no asymmetric stack handling beyond what HUNL already does).
- Bet-size abstraction parity with current HU (½ pot, pot, all-in).
- CLI: `solve --num-players 3 --fixture river_3way.toml`.
- GUI: a 3-handed mode in the setup wizard; results panel updated for 3-column EV display.
- Sanity acceptance tests (see §9).

**Out of scope:**

- 4+ player (combinatorial explosion).
- Full game tree from preflop (preflop 3-handed → tree size measured in trillions of nodes; defer to abstraction work later).
- Asymmetric ICM payouts (SNG/MTT — different terminal utility, separate spec).
- Node-locking for individual players in 3-way (UI/UX gnarly — defer to v2.1 if requested).
- Vector AVX2/NEON kernels for N>2 (the SIMD code in v1.8 assumes pairwise reach-prob mul; widening is a separate optimization spec).

---

## 8. Estimated dev time & risk

**Estimate:** 3-4 weeks (one engineer, full-time equivalent).

| Phase | Duration | What |
|---|---|---|
| 1: Config + tree builder skeleton | 1 week | `MultiwayConfig`, port `mp_betting_tree` skeleton, unit tests on tree shapes |
| 2: ECFR core port | 1 week | `mp_ecfr` adaptation; replace external sampling with our DCFR averaging if feasible, else ship external-sampling path first |
| 3: Showdown + side-pot evaluator | 0.5 week | `SetShowdownPots` port + N-way tie handling |
| 4: CLI + GUI + acceptance tests | 1 week | wiring + Marcus/Sarah/Daniel-style persona fixtures for 3-way |
| Buffer | 0.5 week | known-unknowns |

**Risk: HIGH.** Two structural risks:

1. **Vector form vs external sampling.** Slumbot's `mp_ecfr` is external-sampling (one sampled opponent action per traversal). Our engine is vector-form (full-range traversal). The cleaner port is `mp_vcfr.cpp` but it's almost 2× the LOC. Decision deferred to Phase 2 spike.
2. **Player-count abstraction.** Touching `HUNLConfig` risks regressing the HU path. Mitigation: keep `HUNLConfig` as a thin alias of `MultiwayConfig(num_players=2)` and run the full HU regression suite as a gate before merge.

---

## 9. Acceptance criteria

A1. **Perf:** 3-handed river solve completes in < 5 min on standard fixtures (M-series 8-core, 3 ranges of ~169 combos each).
A2. **Symmetric-EV sanity:** in a fully symmetric 3-handed scenario (identical ranges, equal stacks, equal contributions, symmetric board), all 3 players have equal expected value within numerical tolerance (1e-3 bb).
A3. **Direction-of-aggression sanity:** sets/straights bet; air-range hands fold or check-give-up at frequency > 80% on dry boards. Verified on three persona-style fixtures.
A4. **HU regression:** the existing 2-player HU test suite (PR 9–PR 44) passes bit-identically — no change to HU outputs.
A5. **Approximate-equilibrium disclosure:** GUI shows banner "3-handed: approximate equilibrium (CFR not guaranteed to converge for ≥3 players)." `USAGE.md` documents the caveat.
A6. **License attribution:** CHANGELOG + THIRD_PARTY_NOTICES updated; ported files have per-file MIT attribution headers.

---

## 10. Migration path

**Phase 1 — Config.** Extend `HUNLConfig` (or introduce `MultiwayConfig` alongside) to accept `num_players`. HU path locked at N=2; new N=3 code path gated by feature flag during dev.

**Phase 2 — Port `mp_ecfr` core.** Translate the C++ traversal into Python/Rust matching our DCFR style. Decide vector vs external sampling at the start of this phase based on a spike.

**Phase 3 — Showdown + side-pot evaluator.** Port `SetShowdownPots`. Implement N-way tie-handling (split pots, odd-chip rule per `mp_betting_tree.cpp` comment line 62: "Probably need to honor some chopping rules that dictate who gets the extra chip").

**Phase 4 — CLI + GUI surface.** `--num-players 3` flag. Three-column EV display. Setup wizard updated. Marcus / Sarah / Daniel persona fixtures translated to 3-way and run as acceptance gates.

---

## 11. Defer vs ship — recommendation

**Defer to v1.9 (or v2.0).** Order of operations:

1. Ship v1.7.1 (audit-cleared rectifications).
2. Land v1.8 SIMD work (NEON kernels — separate spec).
3. Spike Phase 1 + Phase 2 vector-vs-external decision (~3 days).
4. If spike clean → commit to v1.9. If spike reveals API-breaking changes → tag v2.0 and bundle with other breaking changes.

**Why not earlier:** every persona-tested HU feature gained from the v1.7.x stability work. Building multiway on a stable HU base reduces blast radius.

**Why not never:** this is the single feature no competitor offers for free with a GUI. It's the headline marketing item for v2.0.

---

## 12. Alternatives considered

| Alternative | Verdict | Reason |
|---|---|---|
| Deep CFR for multiway (NN-based) | Rejected | Original plan rejected NN approaches; opaque, hard to verify, hard to ship. |
| Cluster compute (à la Pluribus) | Rejected | Out of reach for consumer hardware; we ship to laptops. |
| Stay at HU only | Rejected | We're already PioSolver-class at HU. Multiway is the only available headline differentiator. |
| Port a different multiway codebase | Rejected | slumbot2019 is the only MIT-licensed multiway CFR with a complete betting-tree builder. Other multiway research code is academic-only or unlicensed. |
| Approximate via 3 × HU pairwise solves | Rejected | Mathematically incorrect — pairwise EV doesn't compose to 3-way EV when side pots are involved. |

---

## 13. Open questions (resolve during Phase 2 spike)

- Vector-form (port `mp_vcfr`) vs external-sampling (port `mp_ecfr`) — which fits our DCFR averaging best?
- Do we need bucket abstraction (slumbot uses it heavily) or can full-range vector form work without bucketing for 3-handed river?
- Tie/odd-chip handling: do we ship a specific rule (high-card-wins, position-wins) or document as undefined and let the user pick?

---

## 14. References

- Upstream: `/Users/ashen/Desktop/poker_solver/references/code/slumbot2019/`
- Upstream license: `references/code/slumbot2019/LICENSE` (MIT, Eric Jackson 2019)
- OSS comparison context: `docs/oss_competitor_comparison_2026-05-23.md`
- Memory notes: `feedback_research_first_failure_protocol.md`, `feedback_persona_time_budgets.md`
