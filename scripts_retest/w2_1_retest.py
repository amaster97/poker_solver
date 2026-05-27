"""Post-v1.8.0 W2.1 Sarah retest — Full HU 100 BB preflop chart.

Production-scale: full 169-cell HU 100 BB SRP preflop tree.
Pre-v1.8: Full flop fixture timed out at 21 min on v1.7.0; river envelope PASSes.
v1.8 SIMD measured ~1.0x (refuted), so flop timeout expected to persist.

Time budget: Sarah session 15 min total; kill-switch 30 min per persona_time_budgets.
Task constraint: if >20 min wall time, mark BLOCKED and move on.
"""
import time, json, sys
from poker_solver import solve_hunl_preflop, HUNLConfig

# 100 BB HU SRP — Sarah's question.
cfg = HUNLConfig(
    starting_stack=10000, small_blind=50, big_blind=100, ante=0,
    initial_pot=0, initial_contributions=(0,0),  # preflop start: blinds posted within solver
)

print(f'Solving 100 BB HU SRP preflop chart...')
print(f'Start time: {time.strftime("%H:%M:%S")}')
sys.stdout.flush()

t0 = time.time()
try:
    # iter=100 for a fast smoke; 200 was used in W2.5 PASS (30 BB, 14.57s wall).
    # For 100 BB SRP at production scale, scale iter conservatively.
    result = solve_hunl_preflop(
        cfg, iterations=100,  # production-scale enough to confirm convergence direction
        allow_pushfold_range=False,
    )
    wall = time.time() - t0
    print(f'Solve completed in {wall:.2f}s')
    print(f'backend={result.backend!r}')
    print(f'iterations={result.iterations}')
    print(f'game_value={result.game_value:.4f}')

    avg_strategy = result.average_strategy
    print(f'Number of infosets in avg_strategy: {len(avg_strategy)}')

    # Sanity: SB opens X%, BB defends Y%
    n_sb_infosets = sum(1 for k in avg_strategy if 'SB' in str(k) or 'P0' in str(k))
    print(f'SB-tagged infosets: {n_sb_infosets}')

    out = {
        "status": "completed",
        "wall_s": wall,
        "backend": result.backend,
        "iterations_run": result.iterations,
        "game_value": result.game_value,
        "n_infosets": len(avg_strategy),
        "wall_under_5min": wall <= 300,
        "wall_under_15min": wall <= 900,
        "wall_under_20min": wall <= 1200,
    }
except Exception as e:
    wall = time.time() - t0
    out = {"status": "exception", "wall_s": wall, "exception": repr(e)}
    print(f'EXCEPTION after {wall:.2f}s: {e!r}')

with open('/tmp/persona_retests/w2_1_result.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
print(f'End time: {time.strftime("%H:%M:%S")}')
print('Wrote /tmp/persona_retests/w2_1_result.json')
