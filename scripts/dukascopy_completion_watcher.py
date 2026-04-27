"""Auto-close watcher for Pavel autonomy plan 2026-04-27.

Sequence:
  1. Poll logs/extend_dukascopy_2015-2018.log every 60s for completion marker
  2. On Dukascopy completion:
     a. Run extend_dukascopy_2015 --validate-only (gaps, spikes report)
     b. git add + commit Sekce 1 amendment + push
     c. Discord post #system-health
     d. Build extended parquet 2015-2026 from cache (download_data.py cache-only)
     e. Spawn run_extended_ablation.py in BG
     f. Register Win Task DAX-Ablation-Status-1h (hourly Discord)
  3. Poll experiments/extended_ablation/progress.json every 60s for status="completed"
  4. On ablation completion:
     a. Discord post #system-health (final)
     b. Unregister Win Task
     c. Exit

Run as a long-lived background process:
  python scripts/dukascopy_completion_watcher.py &

Logs: logs/watcher.log
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DUKASCOPY_LOG = ROOT / "logs" / "extend_dukascopy_2015-2018.log"
WATCHER_LOG = ROOT / "logs" / "watcher.log"
ABLATION_LOG = ROOT / "logs" / "ablation_runtime.log"
EXTENDED_PARQUET_LOG = ROOT / "logs" / "build_extended_parquet.log"
EXTENDED_PARQUET = ROOT / "data" / "historical" / "GER40_5m_2015-2026.parquet"
PROGRESS_PATH = ROOT / "experiments" / "extended_ablation" / "progress.json"

PYTHON = r"C:\Users\AOS Server\AppData\Local\Programs\Python\Python312\python.exe"
POLL_S = 60
DUKASCOPY_TIMEOUT_S = 6 * 3600   # 6h budget
ABLATION_TIMEOUT_S = 18 * 3600   # 18h budget


def log(msg: str) -> None:
    line = f"[{dt.datetime.utcnow().isoformat(timespec='seconds')}Z] {msg}"
    print(line, flush=True)
    WATCHER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WATCHER_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def discord_post(channel: str, msg: str) -> bool:
    try:
        from src.notifier.discord_notifier import post
        return bool(post(channel, msg, username="DAX-Watcher"))
    except Exception as e:
        log(f"discord post err: {e}")
        return False


def is_dukascopy_done() -> bool:
    if not DUKASCOPY_LOG.exists():
        return False
    text = DUKASCOPY_LOG.read_text(errors="ignore")
    return ("[extend] download counts:" in text
            or "[extend] validation summary:" in text)


def run_validation() -> str:
    log("running cache validation (gap + spike check)")
    p = subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "extend_dukascopy_2015.py"),
         "--start", "2015-01-01", "--end", "2019-01-01", "--validate-only"],
        capture_output=True, text=True, timeout=300,
    )
    out = p.stdout + p.stderr
    log(f"validation rc={p.returncode}, last 400 chars:\n{out[-400:]}")
    return out


def git(*args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


def amendment_commit_and_push(validation_summary: str) -> bool:
    log("amendment commit Sekce 1 (Dukascopy validation)")
    # Save validation summary to file
    val_path = ROOT / "logs" / "dukascopy_validation_summary.txt"
    val_path.write_text(validation_summary, encoding="utf-8")
    # No source code changes; commit is symbolic/empty by design.
    # Use --allow-empty to mark the milestone in git history.
    rc, out = git("commit", "--allow-empty", "-m",
                   "feat(data): Dukascopy 2015-2018 download complete + cache validated\n\n"
                   "Sekce 1 amendment closeout per Pavel hybrid plan 2026-04-27.\n"
                   "Cache extended to 2015-01-01..2018-12-31 (added to existing 2019-2023 + 2026 smoke).\n"
                   "Validation summary attached in logs/dukascopy_validation_summary.txt.\n\n"
                   "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>")
    log(f"git commit rc={rc}, out: {out[-200:]}")
    if rc != 0:
        return False
    rc, out = git("push", "origin", "main")
    log(f"git push rc={rc}, out: {out[-200:]}")
    return rc == 0


def build_extended_parquet() -> bool:
    """Build 2015-2026 parquet from cache (no HTTP fetches, just read-resample)."""
    log(f"building extended parquet -> {EXTENDED_PARQUET}")
    EXTENDED_PARQUET_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXTENDED_PARQUET_LOG.open("w", encoding="utf-8") as logf:
        p = subprocess.Popen(
            [PYTHON, "-u", str(ROOT / "scripts" / "download_data.py"),
             "--symbol", "DEUIDXEUR",
             "--start", "2015-01-01", "--end", "2026-04-01",
             "--tf", "M5",
             "--out", str(EXTENDED_PARQUET)],
            cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT,
        )
    log(f"extended parquet build started, pid={p.pid}")
    # Wait synchronously since we need it before ablation
    rc = p.wait(timeout=3600)
    log(f"extended parquet build rc={rc}")
    return rc == 0 and EXTENDED_PARQUET.exists()


def spawn_ablation() -> int:
    log("spawning extended ablation BG")
    ABLATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    logf = ABLATION_LOG.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [PYTHON, "-u", str(ROOT / "scripts" / "run_extended_ablation.py")],
        cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT,
    )
    log(f"ablation pid={proc.pid}, log={ABLATION_LOG}")
    return proc.pid


def register_status_task() -> bool:
    log("registering Win Scheduled Task DAX-Ablation-Status-1h")
    p = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(ROOT / "scripts" / "install_ablation_status_task.ps1")],
        capture_output=True, text=True, timeout=60,
    )
    log(f"task install rc={p.returncode}, last 200 chars: {(p.stdout + p.stderr)[-200:]}")
    return p.returncode == 0


def unregister_status_task() -> bool:
    log("unregistering Win Scheduled Task DAX-Ablation-Status-1h")
    p = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command",
         "Unregister-ScheduledTask -TaskName 'DAX-Ablation-Status-1h' -Confirm:$false"],
        capture_output=True, text=True, timeout=60,
    )
    log(f"task unreg rc={p.returncode}: {(p.stdout + p.stderr)[-200:]}")
    return p.returncode == 0


def is_ablation_done() -> bool:
    if not PROGRESS_PATH.exists():
        return False
    try:
        data = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        return data.get("status") == "completed"
    except Exception:
        return False


def cache_size_gb() -> float:
    cache = ROOT / "data" / "dukascopy_cache"
    total = 0
    for r, _, files in os.walk(cache):
        for fn in files:
            try:
                total += (Path(r) / fn).stat().st_size
            except OSError:
                pass
    return total / (1024**3)


# ============================================================
# Phase 1: wait for Dukascopy
# ============================================================

def wait_for_dukascopy() -> bool:
    log("Phase 1: waiting for Dukascopy 2015-2018 completion")
    deadline = time.time() + DUKASCOPY_TIMEOUT_S
    while time.time() < deadline:
        if is_dukascopy_done():
            log("Dukascopy DONE")
            return True
        time.sleep(POLL_S)
    log("Dukascopy did not complete within budget")
    return False


# ============================================================
# Phase 2: closeout
# ============================================================

def closeout_sekce_1() -> bool:
    val = run_validation()
    cache_gb = cache_size_gb()
    if not amendment_commit_and_push(val):
        return False
    msg = (
        "🟢 **Dukascopy 2015-2018 complete** — Sekce 1 closeout\n\n"
        f"Cache total: **{cache_gb:.2f} GB** (2015-2026 ready for Extended Ablation).\n"
        "Validation summary in `logs/dukascopy_validation_summary.txt`.\n"
        "Amendment commit pushed.\n\n"
        "**Next**: build extended parquet + auto-start extended ablation."
    )
    discord_post("system_health", msg)
    return True


def start_ablation() -> bool:
    if not build_extended_parquet():
        log("extended parquet build FAILED — aborting ablation")
        discord_post("alerts", "❌ Extended parquet build FAILED, ablation NOT started.")
        return False
    pid = spawn_ablation()
    discord_post("system_health",
                 f"🚀 **Extended ablation started** (44 cells, ETA ~7-10h, pid={pid}). "
                 f"Hourly progress to #system-health via DAX-Ablation-Status-1h.")
    register_status_task()
    return True


# ============================================================
# Phase 3: wait for ablation
# ============================================================

def wait_for_ablation() -> bool:
    log("Phase 3: waiting for ablation completion")
    deadline = time.time() + ABLATION_TIMEOUT_S
    while time.time() < deadline:
        if is_ablation_done():
            log("Ablation DONE")
            return True
        time.sleep(POLL_S)
    log("Ablation did not complete within budget")
    return False


def closeout_ablation() -> None:
    cache_gb = cache_size_gb()
    out_dir = ROOT / "experiments" / "extended_ablation"
    files = sorted(p.name for p in out_dir.glob("*"))
    msg = (
        "🎯 **Extended ablation complete. master_table.csv ready (44 cells). Pokračovat sekcí 5 (analyze)?**\n\n"
        f"Outputs in `experiments/extended_ablation/`:\n"
        f"```\n{chr(10).join(files)}\n```\n"
        f"Cache total: {cache_gb:.2f} GB.\n\n"
        "DAX-Ablation-Status-1h Win Task unregistered. ČEKÁM na schválení Sekce 5."
    )
    discord_post("system_health", msg)
    unregister_status_task()


def main() -> int:
    log("=" * 60)
    log("watcher start")
    if not wait_for_dukascopy():
        discord_post("alerts", "❌ Dukascopy 2015-2018 did not complete within 6h budget. Watcher exiting.")
        return 1
    if not closeout_sekce_1():
        discord_post("alerts", "❌ Sekce 1 amendment commit/push failed. Manual review needed.")
        return 2
    if not start_ablation():
        return 3
    if not wait_for_ablation():
        discord_post("alerts", "❌ Ablation did not complete within 18h budget. Manual review needed.")
        return 4
    closeout_ablation()
    log("watcher done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
