"""W3.5 PoC explicit-combo replication on v1.8.0.

Per W3_5_TRUE_nash_v1_5_1.md, use the exact 15 no-flush combos:
AhAd, AhAc, KhKd, QhQd, JhJd, ThTd, ThTc, 8h8d, 8h8c, 6h6d, 9h9d, 7h7d,
KhQd, KhJd, AhKd.

If AA check ~ 1.0 on this setup, the PoC's result reproduces and the class-name
API result is a range-setup mismatch (not a wrapper bug). If AA check stays
at ~0.3, it's a v1.8.0 wrapper regression vs v1.5.1.
"""
import time, json
from poker_solver import Card, HUNLConfig, Street
from poker_solver._rust import solve_range_vs_range_rust
from poker_solver.hunl import _serialize_hunl_config
from poker_solver.card import card_to_int

cfg = HUNLConfig(
    starting_stack=10000, small_blind=50, big_blind=100, ante=0,
    starting_street=Street.RIVER,
    initial_board=tuple(Card.from_str(c) for c in ('Ts','8s','6s','4c','2d')),
    initial_pot=200, initial_contributions=(100,100),
    initial_hole_cards=(), postflop_raise_cap=2,
    bet_size_fractions=(0.33,0.75,1.50), include_all_in=False,
)

# 15 explicit combos from W3_5_TRUE_nash_v1_5_1.md "Hero / villain ranges" table.
combos_str = ['AhAd', 'AhAc', 'KhKd', 'QhQd', 'JhJd',
              'ThTd', 'ThTc', '8h8d', '8h8c', '6h6d',
              '9h9d', '7h7d', 'KhQd', 'KhJd', 'AhKd']
combos = [(Card.from_str(c[:2]), Card.from_str(c[2:])) for c in combos_str]
print(f'Explicit combos: {combos_str}')
print(f'Count: {len(combos)}')

# Convert to format the Rust func expects (tuples of card-int pairs)
# card_to_int is imported from poker_solver.card above
sample = combos[0]
print(f'Sample combo card type: {type(sample[0])}, attrs: {[a for a in dir(sample[0]) if not a.startswith("_")][:10]}')

config_json = _serialize_hunl_config(cfg)
print(f'config_json keys: {list(config_json.keys()) if isinstance(config_json, dict) else "string"}')

# Try the rust call
import json as _j
if isinstance(config_json, str):
    pass
else:
    config_json = _j.dumps(config_json)

t0 = time.time()
try:
    # Convert combos to int pairs as expected by Rust binding
    combos_int = [[card_to_int(c[0]), card_to_int(c[1])] for c in combos]
    print(f'First combo as ints: {combos_int[0]}')
    result = solve_range_vs_range_rust(
        config_json,
        500,  # iterations (positional)
        1.5, 0.0, 2.0,  # alpha, beta, gamma
        combos_int, combos_int,  # p0_holes, p1_holes
    )
    wall = time.time() - t0
    print(f'Solve completed in {wall:.2f}s')
    print(f'Keys in result: {list(result.keys())}')
    print(f'backend: {result.get("backend")}')
    print(f'hand_count: {result.get("hand_count_per_player")}')

    # Find AA strategy
    avg_strat = result.get('average_strategy', {})
    print(f'Avg strategy entries: {len(avg_strat)}')
    aa_keys = [k for k in avg_strat if 'AhAd' in k or 'AhAc' in k][:3]
    for k in aa_keys:
        v = avg_strat[k]
        print(f'  {k[:80]}... -> {v}')

    out = {
        "status": "completed",
        "wall_s": wall,
        "n_combos": len(combos),
        "iterations": 500,
        "backend": result.get('backend'),
        "hand_count_per_player": result.get('hand_count_per_player'),
        "n_strategy_entries": len(avg_strat),
        "sample_aa_keys": [(k, v) for k, v in list(avg_strat.items())[:3]],
    }
except Exception as e:
    wall = time.time() - t0
    print(f'EXCEPTION: {e!r}')
    out = {"status": "exception", "wall_s": wall, "exception": repr(e)}

with open('/tmp/persona_retests/w3_5_poc_explicit_result.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
print('Wrote /tmp/persona_retests/w3_5_poc_explicit_result.json')
