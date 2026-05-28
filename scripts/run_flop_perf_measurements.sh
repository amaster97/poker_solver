#!/usr/bin/env bash
# Run flop subgame perf measurements with peak-RSS watchers.
#
# Each config: spawns the python script + a watcher that samples ps -o rss
# every 30s and tracks peak. Hard 20-min wall budget enforced via timeout.
#
# Usage: ./scripts/run_flop_perf_measurements.sh <top_k> <iters> <label>

set -euo pipefail

TOP_K=$1
ITERS=$2
LABEL=$3

WORKTREE="/Users/ashen/Desktop/poker_solver_worktrees/flop-perf-measurement"
LOGDIR="$WORKTREE/.perf_logs"
mkdir -p "$LOGDIR"

JSON_OUT="$LOGDIR/${LABEL}.json"
LOG="$LOGDIR/${LABEL}.log"
RSS_LOG="$LOGDIR/${LABEL}.rss"

cd "$WORKTREE"
export PYTHONPATH="$WORKTREE"

# Start python process in background.
python scripts/measure_flop_subgame_perf.py \
    --top-k "$TOP_K" \
    --iters "$ITERS" \
    --label "$LABEL" \
    --json-out "$JSON_OUT" \
    > "$LOG" 2>&1 &
PYPID=$!
echo "[${LABEL}] started python pid=${PYPID}"
echo "0 0 0" > "$RSS_LOG"  # elapsed_s peak_rss_kb current_rss_kb

# Watcher: sample ps -o rss every 30s, track peak.
(
    PEAK=0
    START_TS=$(date +%s)
    while kill -0 "$PYPID" 2>/dev/null; do
        RSS=$(ps -o rss= -p "$PYPID" 2>/dev/null | tr -d ' ' || echo "0")
        if [[ -z "$RSS" || "$RSS" == "0" ]]; then
            sleep 30
            continue
        fi
        if [[ "$RSS" -gt "$PEAK" ]]; then
            PEAK=$RSS
        fi
        NOW_TS=$(date +%s)
        ELAPSED=$((NOW_TS - START_TS))
        echo "$ELAPSED $PEAK $RSS" >> "$RSS_LOG"
        sleep 30
    done
) &
WATCHPID=$!
echo "[${LABEL}] watcher pid=${WATCHPID}"

# 20-minute hard wall budget
HARD_LIMIT=1200
START_TS=$(date +%s)

while kill -0 "$PYPID" 2>/dev/null; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TS))
    if [[ "$ELAPSED" -gt "$HARD_LIMIT" ]]; then
        echo "[${LABEL}] TIMEOUT at ${ELAPSED}s — killing pid=${PYPID}"
        kill -9 "$PYPID" 2>/dev/null || true
        sleep 1
        kill -9 "$WATCHPID" 2>/dev/null || true
        echo "{\"label\":\"${LABEL}\",\"top_k\":${TOP_K},\"iters\":${ITERS},\"status\":\"timeout\",\"wall_s\":${ELAPSED}}" > "$JSON_OUT"
        wait 2>/dev/null || true
        exit 124
    fi
    sleep 5
done

wait "$PYPID"
PYRC=$?
kill -9 "$WATCHPID" 2>/dev/null || true
wait 2>/dev/null || true

echo "[${LABEL}] python exit=${PYRC}"
tail -3 "$RSS_LOG"
echo "[${LABEL}] DONE — see ${LOG} and ${JSON_OUT}"
exit "$PYRC"
