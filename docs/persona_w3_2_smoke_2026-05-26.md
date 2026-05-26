# Persona W3.2 (exploitative best-response) — Smoke Test 2026-05-26

**Status:** PASS — `solve_best_response()` + `poker-solver best-response`
CLI exercised end-to-end against a Kuhn opponent fixture; output is
sensible and matches Kuhn theory.

**Reclassification:** W3.2 was previously BLOCKED on the absence of a
best-response public API. PR 76 (`feee974`, PR #38) landed
`solve_best_response()` at `poker_solver/solver.py:442` and a
`poker-solver best-response` CLI subcommand. With this in place, the
W3.2 workflow ("Sarah — exploitative play vs a fixed villain") is
**empirically PASS** for the Python public API + CLI surface area; the
remaining persona-test scope is downstream UI / workflow validation,
not the solver layer.

## Smoke checks executed

### 1. Import works

```
$ python -c "from poker_solver.solver import solve_best_response; \
    print('OK:', solve_best_response.__doc__[:80])"
OK: Compute hero's deterministic best-response against a fixed opponent.

PR 76 — ex
```

(The shimmed `poker-solver` binary on the user's PATH has a stale
shebang and errors out with `ModuleNotFoundError: No module named
'poker_solver'`; running via `python -m poker_solver.cli` works
correctly. This is an unrelated pyenv-shim issue and is not blocking
on the API surface itself.)

### 2. CLI subcommand exists

```
$ python -m poker_solver.cli best-response --help
usage: poker-solver best-response [-h] --opponent OPPONENT
                                  --hero-position {SB,BB}
                                  --game {hunl,kuhn,leduc}
                                  [--hunl-mode {tiny_subgame,postflop}]
                                  [--board BOARD] [--stacks STACKS]
                                  [--bet-sizes BET_SIZES]
                                  [--abstraction ABSTRACTION]
                                  [--output OUTPUT] [--json]
...
```

### 3. End-to-end run against Kuhn uniform opponent

**Opponent fixture** (`/tmp/kuhn_uniform_opponent.json`): uniform
50/50 over all 12 Kuhn infosets — the maximally exploitable strategy.

```json
{
  "format_version": "1.0",
  "game_id": "kuhn",
  "strategy": {"11|": [0.5, 0.5], "12|p": [0.5, 0.5], ...}
}
```

**Hero = SB (player 0):**

```
$ python -m poker_solver.cli best-response \
    --game kuhn \
    --opponent /tmp/kuhn_uniform_opponent.json \
    --hero-position SB --json
{
  "exploit_gap_bb": 0.375,
  "exploit_gap_mbb": 375.0,
  "exploit_value_bb": 0.5,
  "game": "kuhn",
  "hero_infoset_count": 6,
  "hero_player": 0,
  "hero_position": "SB",
  "on_strategy_value_bb": 0.12500000000000003,
  "opponent_infoset_count": 12
}
```

**Hero = BB (player 1):**

```
$ python -m poker_solver.cli best-response \
    --game kuhn \
    --opponent /tmp/kuhn_uniform_opponent.json \
    --hero-position BB --json
{
  "exploit_gap_bb": 0.5416666666666666,
  "exploit_gap_mbb": 541.6666666666666,
  "exploit_value_bb": 0.4166666666666666,
  "game": "kuhn",
  "hero_infoset_count": 6,
  "hero_player": 1,
  "hero_position": "BB",
  "on_strategy_value_bb": -0.12500000000000003,
  "opponent_infoset_count": 12
}
```

## Verdict

- Import: PASS
- CLI subcommand: PASS
- End-to-end execution: PASS
- Output sanity: PASS — both hero seats produce strictly-positive
  `exploit_gap_bb` (hero playing BR strictly dominates hero playing
  uniform when villain is uniform), `exploit_value_bb` > 0 for SB
  (consistent with Kuhn SB advantage at equilibrium), and
  `hero_infoset_count = 6` (half of the 12 total Kuhn infosets — the
  hero side only).

**W3.2 reclassification:** BLOCKED → PASS for the solver/CLI layer.

## Notes / honest limits

- This smoke only covers Kuhn. Leduc and HUNL postflop are reachable
  via the same CLI (`--game leduc`, `--game hunl --hunl-mode
  tiny_subgame`) but were not exercised in this smoke pass.
- The shimmed `poker-solver` binary is broken on this system —
  unrelated to PR 76. Filed for follow-up.
- The `--output` flag was not exercised here; only stdout JSON
  emission was verified.

**Reference:** PR 76 commit `feee974`, merged via PR #38, 2026-05-25.
