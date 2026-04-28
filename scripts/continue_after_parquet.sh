#!/usr/bin/env bash
# Continuation watcher — assumes parquet build is in progress.
# 1) wait until extended parquet ready
# 2) spawn ablation BG
# 3) register Win Task
# 4) Discord post #system-health (Sekce 1 closeout + ablation start)
# 5) wait until ablation done
# 6) final Discord post + unregister Win Task
set -u

ROOT="C:/Users/AOS Server/dax-ftmo-bot"
PYTHON="C:/Users/AOS Server/AppData/Local/Programs/Python/Python312/python.exe"
PARQUET="$ROOT/data/historical/GER40_5m_2015-2026.parquet"
ABLATION_LOG="$ROOT/logs/ablation_runtime.log"
PROGRESS="$ROOT/experiments/extended_ablation/progress.json"
WATCHER_LOG="$ROOT/logs/watcher.log"

log() {
    echo "[$(date -u +%FT%TZ)] $*" | tee -a "$WATCHER_LOG"
}

discord() {
    local channel="$1"
    local msg="$2"
    "$PYTHON" -c "
import sys, os
sys.path.insert(0, r'$ROOT')
from src.notifier.discord_notifier import post
ok = post('$channel', os.environ.get('MSG', ''), username='DAX-Watcher')
print('discord post ok:', ok)
" 2>&1
}

log "continuation watcher start"

# Phase 2: wait for extended parquet
log "Phase 2: waiting for extended parquet at $PARQUET"
DEADLINE=$(( $(date +%s) + 5400 ))   # 90 min budget (full re-run from cache)
while [ ! -f "$PARQUET" ]; do
    if [ $(date +%s) -gt $DEADLINE ]; then
        log "extended parquet build timeout (90 min)"
        exit 1
    fi
    sleep 30
done
SIZE=$(stat -c %s "$PARQUET" 2>/dev/null || echo 0)
log "extended parquet ready: $SIZE bytes"

# Phase 3: spawn ablation
log "Phase 3: spawning ablation"
"$PYTHON" -u "$ROOT/scripts/run_extended_ablation.py" > "$ABLATION_LOG" 2>&1 &
ABLATION_PID=$!
log "ablation pid=$ABLATION_PID, log=$ABLATION_LOG"

# Phase 4: register Win Task
log "Phase 4: registering Win Task DAX-Ablation-Status-1h"
powershell -NoProfile -ExecutionPolicy Bypass -File "$ROOT/scripts/install_ablation_status_task.ps1" \
    > "$ROOT/logs/install_ablation_task.log" 2>&1
log "task install rc=$?"

# Phase 5: Discord post combined
MSG="🟢 **Sekce 1 closeout + ablation started**

Dukascopy 2015-2018 download complete (commit \`52f7099\`).
Extended parquet 2015-2026 ready (size $SIZE bytes).
Extended ablation BG started (pid $ABLATION_PID, ETA ~7-10h).

Win Task \`DAX-Ablation-Status-1h\` registered — hourly progress to \`#system-health\`.

⚠️ Validation flags from cache check:
- trading_hour_coverage: 62.32% (target >99%)
- spike_count_3sigma: 54238
Pavel review needed before Sekce 5."
MSG="$MSG" discord "system_health" "$MSG"

# Phase 6: wait for ablation completion
log "Phase 6: waiting for ablation completion (status=completed in progress.json)"
DEADLINE=$(( $(date +%s) + 18 * 3600 ))   # 18h budget
while true; do
    if [ -f "$PROGRESS" ]; then
        STATUS=$("$PYTHON" -c "import json; print(json.load(open(r'$PROGRESS')).get('status', 'unknown'))" 2>/dev/null || echo unknown)
        if [ "$STATUS" = "completed" ]; then
            break
        fi
    fi
    if [ $(date +%s) -gt $DEADLINE ]; then
        log "ablation budget exceeded (18h)"
        MSG="❌ Ablation did not complete within 18h budget. Manual review needed."
        MSG="$MSG" discord "alerts" "$MSG"
        exit 4
    fi
    sleep 60
done
log "ablation DONE"

# Phase 7: final Discord + unregister
OUT_DIR="$ROOT/experiments/extended_ablation"
FILES=$(ls "$OUT_DIR" | tr '\n' ' ')
MSG="🎯 **Extended ablation complete. master_table.csv ready (44 cells). Pokračovat sekcí 5 (analyze)?**

Outputs in \`experiments/extended_ablation/\`:
\`\`\`
$FILES
\`\`\`

DAX-Ablation-Status-1h Win Task unregistered. ČEKÁM na schválení Sekce 5."
MSG="$MSG" discord "system_health" "$MSG"

powershell -NoProfile -ExecutionPolicy Bypass -Command \
    "Unregister-ScheduledTask -TaskName 'DAX-Ablation-Status-1h' -Confirm:\$false" \
    > "$ROOT/logs/unreg_ablation_task.log" 2>&1
log "task unreg rc=$?"

log "continuation watcher done"
