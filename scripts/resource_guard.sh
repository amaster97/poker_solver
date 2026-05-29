#!/bin/bash
# resource_guard.sh — lightweight CPU/memory watchdog for v1.10 ship burst.
# Samples every SAMPLE_SECS, appends a one-line status to LOGFILE, and prints a
# CRITICAL banner when memory headroom or swap cross danger thresholds.
# Read-only: it never kills anything (orchestrator decides). Run in background.

SAMPLE_SECS="${SAMPLE_SECS:-20}"
LOGFILE="${LOGFILE:-/tmp/poker_resource_guard.log}"
PAGE=16384  # 16 KB pages on Apple Silicon

# Danger thresholds (24 GB machine, OOM-crashed before)
SWAP_WARN_GB="${SWAP_WARN_GB:-3}"
FREEABLE_WARN_GB="${FREEABLE_WARN_GB:-2}"   # free+inactive+speculative below this = danger

echo "resource_guard started pid=$$ sample=${SAMPLE_SECS}s log=$LOGFILE" | tee -a "$LOGFILE"

while true; do
  ts="$(date '+%H:%M:%S')"
  # vm_stat pages
  vmstat="$(vm_stat)"
  free=$(echo "$vmstat"        | awk '/Pages free/        {gsub(/\./,"",$3); print $3}')
  inactive=$(echo "$vmstat"    | awk '/Pages inactive/    {gsub(/\./,"",$3); print $3}')
  spec=$(echo "$vmstat"        | awk '/Pages speculative/ {gsub(/\./,"",$3); print $3}')
  active=$(echo "$vmstat"      | awk '/Pages active/      {gsub(/\./,"",$3); print $3}')
  wired=$(echo "$vmstat"       | awk '/wired down/        {gsub(/\./,"",$4); print $4}')
  compressed=$(echo "$vmstat"  | awk '/occupied by comp/  {gsub(/\./,"",$5); print $5}')
  freeable_gb=$(echo "$free $inactive $spec $PAGE" | awk '{printf "%.2f", ($1+$2+$3)*$4/1073741824}')
  active_gb=$(echo "$active $PAGE" | awk '{printf "%.2f", $1*$2/1073741824}')
  comp_gb=$(echo "${compressed:-0} $PAGE" | awk '{printf "%.2f", $1*$2/1073741824}')
  # swap
  swap_used_gb=$(sysctl -n vm.swapusage 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="used"){gsub(/M/,"",$(i+2)); print $(i+2)/1024; exit}}')
  swap_used_gb="${swap_used_gb:-0}"
  # load + top cpu proc
  load="$(sysctl -n vm.loadavg | tr -d '{}' | awk '{print $1}')"
  topcpu="$(ps -Ao pcpu,comm -r | sed -n 2p | awk '{printf "%s(%s%%)", $2, $1}')"

  flag=""
  swap_hot=$(echo "$swap_used_gb $SWAP_WARN_GB" | awk '{print ($1>$2)?1:0}')
  mem_hot=$(echo "$freeable_gb $FREEABLE_WARN_GB" | awk '{print ($1<$2)?1:0}')
  if [ "$swap_hot" = "1" ] || [ "$mem_hot" = "1" ]; then
    flag="  *** CRITICAL: freeable=${freeable_gb}GB swap=${swap_used_gb}GB — PAUSE heavy work ***"
  fi

  line="$ts | freeable=${freeable_gb}GB active=${active_gb}GB comp=${comp_gb}GB swap=${swap_used_gb}GB load=${load} top=${topcpu}${flag}"
  echo "$line" >> "$LOGFILE"
  [ -n "$flag" ] && echo "$line"
  sleep "$SAMPLE_SECS"
done
