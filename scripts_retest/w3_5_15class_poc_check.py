"""W3.5 15-class control — does the v1.5.1 PoC range still reproduce AA pure-check?

Per W3_5_TRUE_nash_v1_5_1.md, the 15-class symmetric range gives AA check = 1.0000
at 3000 iter. If the 10-class result (AA check = 0.14) is a wrapper bug, the
15-class run should also fail. If 10-class is a Nash-multiplicity / range-shape
artifact (not a bug), 15-class should PASS as the PoC reported.
"""
import time, json
from poker_solver import Card, HUNLConfig, Street, solve_range_vs_range_nash

cfg = HUNLConfig(
    starting_stack=10000, small_blind=50, big_blind=100, ante=0,
    starting_street=Street.RIVER,
    initial_board=tuple(Card.from_str(c) for c in ('Ts','8s','6s','4c','2d')),
    initial_pot=200, initial_contributions=(100,100),
    initial_hole_cards=(), postflop_raise_cap=2,
    bet_size_fractions=(0.33,0.75,1.50), include_all_in=False,
)
# Full 15-class PoC range from W3_5_TRUE_nash_v1_5_1.md
classes = ['AA','KK','QQ','JJ','TT','99','88',
           'AKs','AQs','AJs','KQs','KJs','JTs','98s','87s']
print(f'15-class range: {classes}')

t0 = time.time()
result = solve_range_vs_range_nash(cfg, hero_range=classes, villain_range=classes,
    iterations=500, hero_player=1, compute_exploitability_at_end=True)
wall = time.time() - t0
aa = result.per_class_strategy.get('AA', {})
print(f'15-class @ 500 iter: AA check={aa.get("check",0):.4f}, wall={wall:.1f}s')
print(f'AA strategy: {dict(aa)}')
print(f'Range aggregate check: {result.range_aggregate.get("check",0):.4f}')

out = {
    "wall_s": wall,
    "n_classes": len(classes),
    "iterations": 500,
    "aa_check": aa.get('check', 0),
    "aa_strategy": dict(aa),
    "range_aggregate_check": result.range_aggregate.get('check', 0),
    "exploitability": result.exploitability,
}
with open('/tmp/persona_retests/w3_5_15class_poc_result.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
