"""Post-v1.8.0 W2.4 Sarah retest — batch-solve CSV schema, 3-spot library round-trip.

Pre-v1.8: Library round-trip PASS (3/3 <10ms); CLI batch-solve INCONCLUSIVE-SLOW.
v1.8 SIMD measured ~1.0x (refuted), so CLI batch-solve perf likely unchanged.
"""
import time, json, subprocess, os, tempfile

t0 = time.time()
# Use temporary library to avoid polluting user library.
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    lib_path = f.name

print(f'Using temp library: {lib_path}')

cmd = [
    '.venv/bin/python', '-m', 'poker_solver.cli', 'batch-solve',
    '--input', 'scripts_retest/w2_4_test_spots.csv',
    '--library-path', lib_path,
    '--workers', '1',  # serial, predictable
]
print(f'Cmd: {" ".join(cmd)}')

env = os.environ.copy()
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, env=env)  # 20-min kill switch
wall = time.time() - t0

print(f'Wall: {wall:.2f}s (target <300s = 5 min per Sarah gate)')
print(f'Return code: {proc.returncode}')
print(f'STDOUT:\n{proc.stdout[-1500:]}')
print(f'STDERR (last 500 chars):\n{proc.stderr[-500:]}')

# Cleanup
try:
    os.unlink(lib_path)
except OSError:
    pass

out = {
    "status": "completed" if proc.returncode == 0 else "failed",
    "wall_s": wall,
    "returncode": proc.returncode,
    "stdout_tail": proc.stdout[-2000:],
    "stderr_tail": proc.stderr[-500:],
    "wall_under_5min": wall <= 300,
    "wall_under_15min": wall <= 900,
    "wall_under_20min": wall <= 1200,
}
with open('/tmp/persona_retests/w2_4_result.json', 'w') as fh:
    json.dump(out, fh, indent=2, default=str)
print('Wrote /tmp/persona_retests/w2_4_result.json')
