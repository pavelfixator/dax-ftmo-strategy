#!/usr/bin/env bash
# Phase 0 backtest completion watcher.
# Polls progress.json for status=completed; on completion: commit results,
# Discord post, unregister hourly status task. Budget: 18h.
set -u

ROOT="C:/Users/AOS Server/dax-ftmo-bot"
PYTHON="C:/Users/AOS Server/AppData/Local/Programs/Python/Python312/python.exe"
PROGRESS="$ROOT/experiments/phase0/progress.json"
WATCHER_LOG="$ROOT/logs/phase0_watcher.log"
TREND_LOG="$ROOT/logs/trend_stress.log"

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$WATCHER_LOG"; }

discord() {
    local channel="$1"
    MSG="$2" "$PYTHON" -c "
import sys, os
sys.path.insert(0, r'$ROOT')
from src.notifier.discord_notifier import post
ok = post('$channel', os.environ.get('MSG',''), username='DAX-Watcher')
print('discord:', ok)
"
}

log "phase0 watcher start"

# Wait for trend_stress_test.py first (small job, may be running)
DEADLINE=$(( $(date +%s) + 7200 ))   # 2h budget for stress test
while ! grep -q "verdict:" "$TREND_LOG" 2>/dev/null; do
    if [ $(date +%s) -gt $DEADLINE ]; then
        log "trend_stress test timeout (2h) -- continuing without it"
        break
    fi
    sleep 60
done
log "trend stress test done (or timeout)"

# Wait for Phase 0 backtest completion
log "waiting for Phase 0 backtest completion"
DEADLINE=$(( $(date +%s) + 18 * 3600 ))
while true; do
    if [ -f "$PROGRESS" ]; then
        STATUS=$("$PYTHON" -c "import json; print(json.load(open(r'$PROGRESS')).get('status', 'unknown'))" 2>/dev/null || echo unknown)
        if [ "$STATUS" = "completed" ]; then
            break
        fi
    fi
    if [ $(date +%s) -gt $DEADLINE ]; then
        log "phase0 backtest budget exceeded (18h)"
        MSG="Phase 0 backtest exceeded 18h budget. Manual review needed." discord "alerts" ""
        exit 4
    fi
    sleep 60
done
log "phase0 DONE"

# Run Bonferroni final (uses ablation cells; quick)
log "running bonferroni_final.py"
"$PYTHON" "$ROOT/scripts/bonferroni_final.py" >> "$WATCHER_LOG" 2>&1

# Re-run gate validator (now has rolling + phase0 results)
log "re-running validate_gate_criteria.py"
"$PYTHON" "$ROOT/scripts/validate_gate_criteria.py" >> "$WATCHER_LOG" 2>&1

# Commit + push
log "git add + commit + push"
cd "$ROOT"
git add experiments/phase0 experiments/rolling_30day_decision.md \
        experiments/rolling_30day_histogram.html \
        experiments/trend_stress_test.md \
        experiments/gate_criteria_validation.md \
        experiments/bonferroni_final.csv 2>/dev/null
git commit -m "feat(phase0): v3.3.2.1 full backtest results

Sekce 6 Cast B closeout: full Phase 0 backtest 2015-2026 + Monte Carlo 10K +
walk-forward 6m + rolling 30d validation + trend stress test + Bonferroni
re-evaluation + 17 gate criteria check.

Outputs in experiments/:
  phase0/summary.json, active_cells.csv, walk_forward.csv, progress.json
  rolling_30day_decision.md, rolling_30day_histogram.html
  trend_stress_test.md
  gate_criteria_validation.md
  bonferroni_final.csv

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" >> "$WATCHER_LOG" 2>&1
git push origin main >> "$WATCHER_LOG" 2>&1

# Final Discord post
SUMMARY=$("$PYTHON" -c "
import json
p = json.load(open(r'$PROGRESS'))
s = json.load(open(r'$ROOT/experiments/phase0/summary.json'))
ftmo = s.get('ftmo_compound', {})
mc = s.get('monte_carlo', {})
wf = s.get('walk_forward_summary', {})
print(f\"FTMO: {ftmo.get('ftmo_compliance_pass','?')} | total_pnl USD: {ftmo.get('total_pnl_usd',0):.0f} | max_dd USD: {ftmo.get('max_dd_usd',0):.0f}\")
print(f\"MC: max_dd 5p \${mc.get('max_dd_usd',{}).get('p5',0):.0f}, P(HARD STOP) {mc.get('p_hard_stop',0):.2%}, RoR {mc.get('risk_of_ruin',0):.2%}\")
print(f\"Walk-forward: {wf.get('oos_pass_count',0)}/{wf.get('n_windows',0)} OOS pass\")
print(f\"Elapsed: {s.get('elapsed_s',0):.0f}s\")
")
MSG_FILE=$(mktemp)
{
echo "Sekce 6 Cast B done. Phase 0 backtest hotov."
echo ""
echo "Spec: v3.3.2.1 (4 active cells)"
echo ""
echo "$SUMMARY"
echo ""
echo "Pokracovat sekci 7 (final reports)?"
} > "$MSG_FILE"
MSG=$(cat "$MSG_FILE") "$PYTHON" -c "
import sys, os
sys.path.insert(0, r'$ROOT')
from src.notifier.discord_notifier import post
ok = post('system_health', os.environ.get('MSG',''), username='DAX-Watcher')
print('final discord:', ok)
" >> "$WATCHER_LOG" 2>&1
rm "$MSG_FILE"

# Unregister hourly status task
log "unregistering DAX-Phase0-Status-1h"
powershell -NoProfile -ExecutionPolicy Bypass -Command \
    "Unregister-ScheduledTask -TaskName 'DAX-Phase0-Status-1h' -Confirm:\$false" \
    >> "$WATCHER_LOG" 2>&1

log "phase0 watcher done"
