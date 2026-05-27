# Correct A83 Solver Entrypoint (PR 90 / A83 Track A Retest)

**Date:** 2026-05-26
**Scope:** Identify the CORRECT Python entrypoint for running A83-style
postflop range-vs-range solves end-to-end, given that the CLI's
`solve --hunl-mode postflop` path is broken when `--initial-hole-cards`
is omitted (silent empty-strategy).

---

## TL;DR

| Item | Value |
|---|---|
| Correct entrypoint | `poker_solver._rust.solve_range_vs_range_rust` |
| Where it is used | `tests/test_v1_5_brown_apples_to_apples.py:612-620` |
| Returns real strategies on A83? | YES (per `docs/v1_6_1_dryrun_7.md` line 130, A83 produces 4758 cells) |
| `regret_init_noise` plumbed? | YES, kwarg at position 8 of the PyO3 signature (default `0.0`) |
| Two-run retest wallclock | ~5-6 minutes total (A83 ≈ 160s/run @ 2000 iters) |

---

## 1. The right function

**Python-side binding:** `poker_solver._rust.solve_range_vs_range_rust`

**PyO3 declaration** (`crates/cfr_core/src/lib.rs:423-447`):

```rust
#[pyfunction]
#[pyo3(signature = (
    config_json,        // serialized HUNLConfig (str)
    iterations,         // u32
    alpha,              // f64 — DCFR alpha
    beta,               // f64 — DCFR beta
    gamma,              // f64 — DCFR gamma
    p0_holes=None,      // Option<Vec<[u8; 2]>> — Rust P0's hand list (card ids)
    p1_holes=None,      // Option<Vec<[u8; 2]>> — Rust P1's hand list
    regret_init_noise=0.0,  // f64 — PR 90 A83 Track A
    rng_seed=0,         // u64 — seed for regret-init-noise RNG
))]
fn solve_range_vs_range_rust(...)
```

**Returns** a dict with keys:
- `average_strategy`: `dict[str, list[float]]` — keyed by
  `<hole_string>|<board>|<street>|<history>`
- `iterations`, `wallclock_seconds`, `decision_node_count`,
  `strategy_entry_count`, `hand_count_per_player`, `memory_profile`,
  `backend = "rust_vector"`.

**The hole-string format** is Rust's `exploit::hole_string`
(`crates/cfr_core/src/exploit.rs:490-498`): sort the two `[u8; 2]`
card ids ascending by `card_to_int = rank * 4 + suit`, then render with
`RANKS = "23456789TJQKA"`, `SUITS = "shdc"`. Examples:
- `3sAs` and `3cAc` (note `3` first because card-id `3*4+s < A*4+s`).

---

## 2. Why the CLI path is broken

**CLI postflop path** (`poker_solver/cli.py:375-386`):
```python
elif args.game == "hunl" and getattr(args, "hunl_mode", "") == "postflop":
    from poker_solver.hunl_solver import solve_hunl_postflop
    result = solve_hunl_postflop(
        game.config,
        iterations=args.iterations,
        ...
    )
```

This calls **`solve_hunl_postflop`**, NOT `solve_range_vs_range_rust`.

`solve_hunl_postflop` is the **Python-tier reference solver** that
**requires pinned hole cards** to produce a non-empty strategy. When
`HUNLConfig.initial_hole_cards = ()` (the default), it has no
range-vs-range walker — it walks the betting tree once with empty hole
slots, encounters no decision node where a hand is dealt, and silently
returns an empty `average_strategy` dict.

The **vector-form CFR** (PR 23, `solve_range_vs_range_rust`) is the
opposite: when both `p0_holes` and `p1_holes` are supplied (the v1.5
A83 fixture's range lists), it walks Brown's vector-form CFR through
the betting tree with the full per-hand probability matrix per infoset.
`initial_hole_cards = ()` is the *trigger* for this path, not a bug.

**The CLI does not expose `solve_range_vs_range_rust`** — there is no
`--range-p0` / `--range-p1` flag, and the `--backend rust` switch
routes through `solve()` → `_solve_rust` which is also a scalar /
pinned-hole-cards path. To use the vector-form CFR from a script you
must call the PyO3 binding directly.

---

## 3. How the v1.5 Brown acceptance test invokes it

Reproduced from `tests/test_v1_5_brown_apples_to_apples.py:602-620`
(verbatim, no modification):

```python
config = _build_rust_config_for_spot(spot)
config_json = _serialize_hunl_config(config)

# Fix B (PR 40): Brown's P0 = opener; Rust's P1 = opener.
# Rust P1 gets the opener range (spot.ranges[0]);
# Rust P0 gets the defender range (spot.ranges[1]).
p0_holes = _spot_hand_ids(spot, 1)   # Rust P0 = defender = ranges[1]
p1_holes = _spot_hand_ids(spot, 0)   # Rust P1 = opener   = ranges[0]

rust_result = _rust_solve_rvr(
    config_json,
    ITERATIONS,          # 2000
    DCFR_ALPHA,          # 1.5
    DCFR_BETA,           # 0.0
    DCFR_GAMMA,          # 2.0
    p0_holes,
    p1_holes,
)
rust_strategy = rust_result["average_strategy"]
```

Where `_rust_solve_rvr` resolves to (line 282):
```python
_rust_solve_rvr = getattr(_rust_module, "solve_range_vs_range_rust", None)
```

The config builder (`tests/test_v1_5_brown_apples_to_apples.py:334-361`)
is the key — it constructs an A83 `HUNLConfig` with
`initial_hole_cards=()` (which triggers the RvR path) and the spot's
pot / stack / bet menu / raise cap:

```python
return HUNLConfig(
    starting_stack=int(spot.stack),            # 9500 for A83
    small_blind=50,
    big_blind=100,
    ante=0,
    starting_street=Street.RIVER,
    initial_board=tuple(spot.board),            # ('Ah','8c','3d','Tc','6s')
    initial_pot=pot,                            # 1000 for A83
    initial_contributions=(pot // 2, pot - pot // 2),
    initial_hole_cards=(),                      # triggers vector-form CFR
    postflop_raise_cap=int(spot.max_raises),    # 3 for A83
    bet_size_fractions=tuple(spot.bet_sizes),   # (0.5, 1.0) for A83
    include_all_in=bool(spot.include_all_in),   # True for A83
)
```

The hand list is built by `_spot_hand_ids` (line 364-388):
```python
[[card_to_int(c0), card_to_int(c1)] for combo, _w in spot.ranges[player]]
```

---

## 4. How to set `--regret-init-noise`

NOT a CLI flag (the `--regret-init-noise` argparse flag exists on
`solve` but only flows through `_cmd_solve` to `solve_hunl_postflop`'s
Rust backend variant — which is the wrong solver path for RvR).

For `solve_range_vs_range_rust` it is **kwarg position 8**:
```python
rust_result = solve_range_vs_range_rust(
    config_json, iterations, alpha, beta, gamma,
    p0_holes, p1_holes,
    regret_init_noise=1e-9,   # <-- here
    rng_seed=0,
)
```

`regret_init_noise = 0.0` is bit-identical to the un-perturbed
all-zero `regret_sum` initialization
(`dcfr_vector.rs:182-199`).

---

## 5. Minimal Python script template (~30 lines)

**DO NOT RUN — investigation per task constraints.** Template only.

```python
"""A83 Track A retest: regret_init_noise = 0.0 vs 1e-9.

Bypasses the broken `solve --hunl-mode postflop` CLI path; calls
the PyO3 binding directly with the same arguments
`tests/test_v1_5_brown_apples_to_apples.py` uses.
"""
from poker_solver._rust import solve_range_vs_range_rust
from poker_solver.parity.noambrown_wrapper import load_spots
from poker_solver.card import card_to_int
from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config
from pathlib import Path

REPO = Path("/Users/ashen/Desktop/poker_solver")
spot = next(s for s in load_spots(REPO / "tests/data/river_spots.json")
            if s.id == "dry_A83_rainbow")
pot = int(spot.pot)
cfg = HUNLConfig(
    starting_stack=int(spot.stack), small_blind=50, big_blind=100, ante=0,
    starting_street=Street.RIVER, initial_board=tuple(spot.board),
    initial_pot=pot, initial_contributions=(pot // 2, pot - pot // 2),
    initial_hole_cards=(),
    postflop_raise_cap=int(spot.max_raises),
    bet_size_fractions=tuple(spot.bet_sizes),
    include_all_in=bool(spot.include_all_in),
)
config_json = _serialize_hunl_config(cfg)
p0_holes = [[card_to_int(c0), card_to_int(c1)] for (c0, c1), _w in spot.ranges[1]]
p1_holes = [[card_to_int(c0), card_to_int(c1)] for (c0, c1), _w in spot.ranges[0]]

# Run A: noise = 0.0 (bit-identical baseline).
result_a = solve_range_vs_range_rust(
    config_json, 2000, 1.5, 0.0, 2.0, p0_holes, p1_holes,
    regret_init_noise=0.0, rng_seed=0,
)
# Run B: noise = 1e-9 (Track A perturbation).
result_b = solve_range_vs_range_rust(
    config_json, 2000, 1.5, 0.0, 2.0, p0_holes, p1_holes,
    regret_init_noise=1e-9, rng_seed=0,
)

# Hole-string format = Rust's exploit::hole_string output.
# Card id sort ascending by rank*4+suit, then render with RANKS = "23456789TJQKA"
# and SUITS = "shdc". For A83 we want hand strings "3sAs" and "3cAc".
# (3 is rank-index 1 -> id 4..7; A is rank-index 12 -> id 48..51; 3 < A.)
def per_cell(result, hand_str, history_substr):
    # Keys: "<hole_string>|<board>|<street>|<history>"
    for k, probs in result["average_strategy"].items():
        h, _board, _street, hist = k.split("|")
        if h == hand_str and hist == history_substr:
            return probs
    return None

# Example: dump root (player-1 opens river -> history="") strategies for
# 3sAs and 3cAc; iterate a chosen history_substr too.
for hand in ("3sAs", "3cAc"):
    a = per_cell(result_a, hand, "")  # root open
    b = per_cell(result_b, hand, "")
    print(f"{hand} root  noise=0.0 -> {a}")
    print(f"{hand} root  noise=1e-9 -> {b}")
    if a is not None and b is not None:
        diff_pp = [abs(x - y) * 100 for x, y in zip(a, b)]
        print(f"{hand} root  pp-diff -> {diff_pp}")
```

Notes on the template:
- The hole-string format is **render-from-Rust**; we do NOT control the
  key string — the solver emits it. The matching pattern above is the
  same one `_combo_to_hole_string` produces
  (`tests/test_v1_5_brown_apples_to_apples.py:391-419`).
- For non-root histories use the renderer at
  `tests/test_v1_5_brown_apples_to_apples.py:422-497`
  (`_rust_history_substr_for_canonical`) to convert Brown's canonical
  history tokens to our `<history>` substring; or iterate the
  `result["average_strategy"]` dict directly and split on `|`.
- Player-convention note: per `tests/test_v1_5_brown_apples_to_apples.py:608-610`
  Rust's P1 is the opener on river. If retesting against a particular
  player's strategy, remember `p0_holes` came from `spot.ranges[1]` (defender)
  and `p1_holes` from `spot.ranges[0]` (opener).

---

## 6. Estimated wall-clock

- **A83 Rust solve @ 2000 iterations:** ~160s wall (per
  `docs/v1_6_1_dryrun_7.md` line 104).
- **Two runs (noise=0.0 + noise=1e-9):** ~5-6 minutes wall total.
- **Brown side not needed** (no parity diff in the retest).
- The test docstring's "~30s per spot" estimate is stale (pre-PR 23's
  v1.5.1 perf-regression; the more recent dryrun documents ~160s for
  the A83 spot at the same iteration count).

This fits within a single agent execution window (~25-45 min budget per
`feedback_agent_execution_timeout`), with margin.

---

## 7. Files referenced (absolute paths)

- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — public API exports (note: `solve_range_vs_range_rust` is NOT in `__all__`; it is accessed via `poker_solver._rust`).
- `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` — the PyO3 .so providing the binding.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` (lines 423-520) — PyO3 entrypoint.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs` (lines 803-870) — `solve_range_vs_range_postflop_with_hands` (the function the binding calls).
- `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py` (lines 334-361, 593-620) — reference invocation.
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py` (lines 83-104, 358) — `RiverSpot` dataclass and `load_spots`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` (line 868+) — `_serialize_hunl_config` helper.
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` (lines 375-393) — proof the CLI postflop path calls `solve_hunl_postflop`, not the RvR vector-form solver.
- `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json` — A83 fixture (`dry_A83_rainbow`).
- `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_7.md` (lines 103-104, 128-138) — A83 wall-clock data + 2000-iter cell counts.
</content>
</invoke>