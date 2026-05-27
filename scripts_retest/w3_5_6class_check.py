"""W3.5 6-class control — to verify it matches the prior PASS-at-6-class result."""
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
classes = ['AA','KK','QQ','JJ','TT','99']

t0 = time.time()
result = solve_range_vs_range_nash(cfg, hero_range=classes, villain_range=classes,
    iterations=500, hero_player=1, compute_exploitability_at_end=True)
wall = time.time() - t0

aa = result.per_class_strategy.get('AA', {})
print(f'6-class: AA check={aa.get("check",0):.4f} ({len(classes)}-class, {wall:.1f}s)')
print(f'AA strategy: {dict(aa)}')

# Now compare against 10-class
print('---')
classes10 = ['AA','KK','QQ','JJ','TT','99','88','AKs','AQs','KQs']
t0 = time.time()
result2 = solve_range_vs_range_nash(cfg, hero_range=classes10, villain_range=classes10,
    iterations=500, hero_player=1, compute_exploitability_at_end=True)
wall2 = time.time() - t0
aa2 = result2.per_class_strategy.get('AA', {})
print(f'10-class: AA check={aa2.get("check",0):.4f} ({len(classes10)}-class, {wall2:.1f}s)')
print(f'AA strategy: {dict(aa2)}')

out = {
    "6class": {"aa_check": aa.get("check",0), "wall_s": wall, "aa_strategy": dict(aa)},
    "10class": {"aa_check": aa2.get("check",0), "wall_s": wall2, "aa_strategy": dict(aa2)},
}
with open('/tmp/persona_retests/w3_5_class_compare.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
