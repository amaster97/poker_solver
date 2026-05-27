"""W3.5 PoC explicit-combo, look at ROOT river-open infoset for AA."""
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
combos_str = ['AhAd', 'AhAc', 'KhKd', 'QhQd', 'JhJd',
              'ThTd', 'ThTc', '8h8d', '8h8c', '6h6d',
              '9h9d', '7h7d', 'KhQd', 'KhJd', 'AhKd']
combos = [(Card.from_str(c[:2]), Card.from_str(c[2:])) for c in combos_str]
combos_int = [[card_to_int(c[0]), card_to_int(c[1])] for c in combos]
config_json = _serialize_hunl_config(cfg)

t0 = time.time()
result = solve_range_vs_range_rust(config_json, 3000, 1.5, 0.0, 2.0, combos_int, combos_int)
wall = time.time() - t0
print(f'wall={wall:.2f}s, backend={result["backend"]}, hand_count={result["hand_count_per_player"]}')

avg_strat = result['average_strategy']
# Find root river-open infoset: should be AA combo + empty action history
# Per PoC, BB is the river-first actor (p1 at root) - so look for p1 root
# Actually format is "hole|board|action_history"; root has empty history
print('--- Root infosets (no action history) ---')
for combo in combos_str:
    # Try both player orderings - which player is the actor at root?
    # PoC says "P1 (BB) is first to act on river" — so root infoset belongs to p1
    root_keys = [k for k in avg_strat if k.startswith(combo + '|') and k.endswith('|r')]
    # 'r' = river-open action history (empty subgame history)
    for k in root_keys[:1]:
        strat = avg_strat[k]
        # Number of actions = check + 3 bet sizes = 4
        print(f'  {k} -> check={strat[0]:.4f}  bet_33={strat[1]:.4f}  bet_75={strat[2]:.4f}  bet_150={strat[3]:.4f}')

# Specifically look at AA root
aa_keys = sorted([k for k in avg_strat if (k.startswith('AhAd|') or k.startswith('AhAc|')) and k.endswith('|r')])
print(f'\nAA root keys (river-open): {aa_keys}')
aa_check_total = 0.0
aa_count = 0
for k in aa_keys:
    s = avg_strat[k]
    print(f'  {k}: {s}')
    aa_check_total += s[0]
    aa_count += 1
aa_check_avg = aa_check_total / aa_count if aa_count else 0
print(f'\nAA root check (avg over {aa_count} AA combos at river-open): {aa_check_avg:.4f}')

out = {
    "wall_s": wall,
    "iterations": 3000,
    "backend": result['backend'],
    "hand_count": list(result['hand_count_per_player']),
    "n_strategy_entries": len(avg_strat),
    "aa_root_check_avg": aa_check_avg,
    "aa_root_keys": aa_keys,
    "aa_root_strategies": {k: avg_strat[k] for k in aa_keys},
}
with open('/tmp/persona_retests/w3_5_poc_explicit_root_result.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
