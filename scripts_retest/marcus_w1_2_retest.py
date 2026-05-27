"""Post-v1.8.0 Marcus W1.2 retest — river bluff-catcher Nash check.

Marcus persona, 30s tolerance. JJ on As Tc 5d Jh 8s — solve_range_vs_range_nash
at production scale (10+ class villain range).

Pre-v1.8: PASS via Nash path at 9.19s (JJ defend = 1.0000).
"""
import time, json
from poker_solver import Card, HUNLConfig, Street, solve_range_vs_range_nash

# Marcus's spot: JJ on As Tc 5d Jh 8s, villain bets pot.
# Use 12-class villain range (production-scale).
cfg = HUNLConfig(
    starting_stack=10000, small_blind=50, big_blind=100, ante=0,
    starting_street=Street.RIVER,
    initial_board=tuple(Card.from_str(c) for c in ('As','Tc','5d','Jh','8s')),
    initial_pot=2000, initial_contributions=(1000,1000),
    initial_hole_cards=(), postflop_raise_cap=2,
    bet_size_fractions=(1.0,),  # pot-size bet only
    include_all_in=False,
)

# 10-class villain range (production-scale RvR for Marcus's bluff-catcher question).
classes = ['JJ','AA','KK','QQ','TT','AKs','AQs','AJs','KJs','QJs']

t0 = time.time()
try:
    result = solve_range_vs_range_nash(
        cfg, hero_range=classes, villain_range=classes,
        iterations=200, hero_player=0, compute_exploitability_at_end=True,  # hero = BB facing bet
    )
    wall = time.time() - t0
    print(f'backend={result.backend!r} wall_s={wall:.2f} '
          f'exploit={result.exploitability:.4f}')

    jj = result.per_class_strategy.get('JJ', {})
    jj_call = jj.get('call', 0.0)
    jj_fold = jj.get('fold', 0.0)
    jj_check = jj.get('check', 0.0)
    print(f'JJ on As Tc 5d Jh 8s: call={jj_call:.4f}, fold={jj_fold:.4f}, check={jj_check:.4f}')

    # Marcus 30s budget check
    print(f'Marcus 30s gate: {"PASS" if wall <= 30 else "FAIL"} ({wall:.1f}s)')

    out = {
        "status": "completed",
        "wall_s": wall,
        "backend": result.backend,
        "exploitability": result.exploitability,
        "jj_strategy": dict(jj),
        "jj_call": jj_call,
        "jj_fold": jj_fold,
        "marcus_30s_gate": wall <= 30,
        "marcus_30s_wall_pass": wall <= 30,
        "marcus_5min_session_pass": wall <= 300,
    }
except Exception as e:
    wall = time.time() - t0
    out = {"status": "exception", "wall_s": wall, "exception": repr(e)}
    print(f'EXCEPTION after {wall:.2f}s: {e!r}')

with open('/tmp/persona_retests/marcus_w1_2_result.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
print('Wrote /tmp/persona_retests/marcus_w1_2_result.json')
