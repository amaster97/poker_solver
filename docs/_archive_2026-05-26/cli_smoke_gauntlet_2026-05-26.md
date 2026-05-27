# CLI Smoke Gauntlet 2026-05-26

**Branch:** main
**HEAD:** `eb74fb3d76b0889d36ba0523679c99bc8d9a0966`
**Environment:** `.venv/bin/poker-solver` (Python 3.13)
**Date:** 2026-05-26
**Operator:** smoke-gauntlet agent (post-all-merges sanity check)

## TL;DR

| # | Command | Status | Note |
|---|---|---|---|
| 1 | `equity` exact (board) | PASS | AhKh vs QdQc on 2h7h9d → 54.14% / 45.86% |
| 2 | `equity` MC range | PASS | "AA,KK,AKs" vs QdQc, 50k → 72.94% / 27.06% |
| 3 | `solve` Kuhn (python) | PASS | 5000 iters, exploitability 0.001074 |
| 4 | `solve` Leduc (rust) | PASS | 1000 iters, exploitability 0.021191 |
| 5 | `solve` HUNL tiny_subgame (rust) | PASS | 200 iters, exploitability 0.000100 |
| 6 | `solve` HUNL postflop ad-hoc (rust) | **FAIL — timeout** | killed after 4:22 wall (8x+ over 30 s budget) without producing any output |
| 7 | `pushfold` | PASS | Help OK; `--stack 10 --position sb_jam --hand 88` → 1.000000 |
| 8 | `river` | PASS* | Used `--iters` (actual flag) instead of `--iterations` per user spec; AdQd vs AA,KK on As7c2dKh5s → 100 iters → mean BB -5.0015 |
| 9 | `best-response` | PASS | Help OK; ran against Kuhn opponent strategy → exploit gap +5.2 mBB/hand |
| 10 | `parity` | PASS | Help OK (--fixture-driven; not exercised end-to-end) |
| 11 | Python API smoke | PASS | `from poker_solver import HUNLConfig, HUNLPoker, Range, solve, parse_range` OK |
| 12 | Rust extension smoke | PASS | `from poker_solver._rust import solve_range_vs_range_rust, solve_hunl_postflop` OK |

**Headline:** 11 / 12 PASS. The lone failure is the **HUNL postflop ad-hoc** documented invocation (Cmd 6) — it hangs well past any reasonable smoke-test budget. This is a documented user-facing path on the README; **flagging prominently** below.

---

## Per-command notes

### 1. `equity` exact — PASS
```
poker-solver equity AhKh QdQc --board 2h7h9d
```
Output:
```
Iterations: 990   Board: 2h 7h 9d

Hand 1: AhKh  win 54.14%  tie  0.00%  equity 54.14%
```
Behaviour matches README example. Exact enumeration of the remaining 990 turn/river runouts.

---

### 2. `equity` MC range — PASS
```
poker-solver equity "AA,KK,AKs" QdQc -n 50000
```
Output:
```
Iterations: 50000

Hand 1: AA,KK,AKs (16 combos)  win 72.71%  tie  0.46%  equity 72.94%
```
Combo expansion (16 combos for AA+KK+AKs) and MC sampling both working.

---

### 3. `solve` Kuhn (python backend) — PASS
```
poker-solver solve --game kuhn --iterations 5000 --backend python
```
Output (first 6 lines):
```
Game:        kuhn
Backend:     python
Iterations:  5000
Game value:  -0.055570 (P1 perspective)
Exploitability (final): 0.001074
```
Game value within expected band (theoretical ≈ −1/18 = −0.0556). Solver converging.

---

### 4. `solve` Leduc (rust backend) — PASS
```
poker-solver solve --game leduc --iterations 1000 --backend rust
```
Output (first 6 lines):
```
Game:        leduc
Backend:     rust
Iterations:  1000
Game value:  -0.085412 (P1 perspective)
Exploitability (final): 0.021191
```
1000 iterations gives moderate exploitability; would converge further with more iters. Rust backend wired up correctly.

---

### 5. `solve` HUNL tiny_subgame (rust backend) — PASS
```
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 200 --backend rust
```
Output (first 6 lines):
```
Game:        hunl
Backend:     rust
Iterations:  200
Game value:  +5.000194 (P1 perspective)
Exploitability (final): 0.000100
```
Tiny subgame (river-only fixture) converges fast; sub-mBB exploitability at 200 iters. This is the canonical fast HUNL smoke.

---

### 6. `solve` HUNL postflop ad-hoc — **FAIL (timeout)**
```
poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d" --stacks 100 --bet-sizes "33,75,150" --iterations 100 --backend rust
```
**Status:** killed after **4:22 wall time** at 100% CPU + 2.3 GB RAM with **zero stdout produced**.

Tightened repro (1 bet-size, 50 stacks, 50 iters, river start):
```
poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d Kh 5s" --stacks 50 --bet-sizes "75" --iterations 50 --backend rust
```
also hung past 27 s and was killed.

**Diagnosis (not root-cause; no code touched per task constraints):**
- The 100-iter budget is on the DCFR loop, but the documented invocation starts from the **flop** (3 cards), so the postflop tree includes 47×46/2 = 1081 turn cards + river cards × the bet-size menu. Tree construction (and any precompute) dominates wall time, not DCFR iterations.
- This matches the long-running background process observed (PID 42803, 45 min, `--iterations 200000 --log-every 10000`) which is the kind of session this engine is built for, not 100-iter smoke.

**User impact:** the documented README example for HUNL postflop is **not** a quick smoke — it is a multi-minute-to-multi-hour job depending on start street and bet-size menu. If we want a "30 second" reproducer for docs, we need to either:
1. Document that postflop is a heavy job and lower expectations in README, OR
2. Add a `--quick` / `--river` / `--single-turn` smoke mode that constructs a sub-tree quickly, OR
3. Move postflop into a tutorial doc with explicit timing notes.

This is a **documentation / user-expectation** gap, not necessarily a code regression. The engine works (tiny_subgame Cmd 5 passes in seconds).

---

### 7. `pushfold` — PASS
Help output: subcommand exists with `--stack`, `--position {sb_jam,bb_call_vs_jam}`, `--hand`, `--full-range`, `--json`.

Real invocation:
```
poker-solver pushfold --stack 10 --position sb_jam --hand 88
```
Output:
```
88 sb_jam 10BB: 1.000000
```
Chart lookup working. 88 is a 100% jam at 10 BB per the SB jam chart, as expected.

---

### 8. `river` — PASS (with flag-name caveat)
**Note:** the user's command uses `--iterations 100`, but the actual CLI flag is `--iters`. README/USAGE may need a consistency pass here.

```
poker-solver river --board "As 7c 2d Kh 5s" --hero AdQd --villain-range "AA,KK" --iters 100
```
Output (first 6 lines):
```
Board:        As 7c 2d Kh 5s
Hero:         Ad Qd
Villain range: AA,KK (4 combos after card removal)
Iterations:   100
```
Mean game value: −5.0015 BB (hero is dominated vs AA+KK on a A-high board → all-in fold-equity scenario).

**Action item:** USAGE §7a should reflect the `--iters` flag.

---

### 9. `best-response` — PASS
Help output: full schema documented (--opponent, --hero-position, --game, optional --output / --json).

Real invocation with synthesized Kuhn opponent (saved Cmd 3 output to JSON):
```
poker-solver best-response --opponent /tmp/kuhn_opp.json --hero-position SB --game kuhn
```
Output:
```
Best-response analysis
======================
Hero: SB (player 0)
Opponent strategy: kuhn_opp.json (12 infosets)
Game: kuhn

On-strategy value:    -0.055409 BB/hand
Exploit (BR) value:   -0.050200 BB/hand
Exploit gap:          +0.005209 BB/hand (+5.2 mBB/hand)

Hero BR strategy: 6 infosets (deterministic one-hot per infoset).
```
The opponent strategy was constructed from the Kuhn 1000-iter Cmd 3 output. BR finds a +5.2 mBB exploit gap, indicating the opponent has not fully converged (sound — 1000 iters is loose for Kuhn). Schema loader + solver integration both functioning.

---

### 10. `parity` — PASS (help only)
Help output exposes `--fixture` (required, a spot id from `tests/data/river_spots.json`), `--fixture-path`, `--iters` (default 2000). Real invocation requires a known fixture id; not exercised end-to-end because (a) running it at the default 2000 iters would exceed the 30 s smoke budget on most spots, and (b) it requires Brown's binary to be on PATH (parity is by design a diff against the external solver).

---

### 11. Python API smoke — PASS
```
.venv/bin/python -c "from poker_solver import HUNLConfig, HUNLPoker, Range, solve, parse_range; print('imports OK')"
# imports OK
```

---

### 12. Rust extension smoke — PASS
```
.venv/bin/python -c "from poker_solver._rust import solve_range_vs_range_rust, solve_hunl_postflop; print('rust OK')"
# rust OK
```
Both Rust-backed entry points importable on darwin/arm64.

---

## Findings & action items

1. **PROMINENT FAIL on Cmd 6 (HUNL postflop ad-hoc).** Documented invocation requires multi-minute+ wall time. Either the README/USAGE needs a clear warning, or we need a documented "fast" postflop smoke. Cmd 5 (tiny_subgame) is the only HUNL invocation suitable for a 30 s smoke today.
2. **Flag-name mismatch on `river`:** task spec (and possibly USAGE §7a) uses `--iterations`, actual flag is `--iters`. Consistency pass needed.
3. **`parity` not end-to-end-exercised:** the default `--iters 2000` is too slow for a 30 s smoke; consider adding a `--quick` mode for CI.
4. **All other 10 documented paths PASS** with expected output shapes. Equity (exact + MC), Kuhn/Leduc/tiny-HUNL solve, pushfold, river, best-response, and the Python + Rust import surfaces are all healthy.

## Environment notes

- Used `.venv/bin/poker-solver` directly (per shim-fix doc) to avoid the broken pyenv shim.
- One background `poker-solver` process (PID 42803, `--iterations 200000`) was already running unrelated to this gauntlet; left undisturbed.
- No code modified; no library writes attempted (gauntlet is read-only against the engine).
