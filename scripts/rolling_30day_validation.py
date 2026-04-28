"""Rolling 30-day validation for v3.3.2.1.

For each rolling 30-day window 2015-2026:
  - Count trade-eligible days (regime != UNDEFINED)
  - Count actual trades simulated
  - Build histogram of (trade_eligible_days_per_30d_window)

Decision tree (Pavel spec):
  fail_pct < 5%      → PASS
  fail_pct 5-15%     → WARNING
  fail_pct > 15%     → REQUIRES ADJUSTMENT

A window FAILS if it produces < threshold trade-eligible days. Default threshold:
  required_trade_days_per_30d = 7   (~1.5 trades/day target → ≥10 trades/30d)

Output:
  experiments/rolling_30day_histogram.html  (HTML matplotlib bars)
  experiments/rolling_30day_decision.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.data_feed import BarFeed
from src.strategy.regime import Regime, get_active_regime
from src.strategy.regime.classifier import (
    classify_regime_raw, derive_signals_from_market_data,
)
from src.strategy.setups.orb_dax import aggregate_daily
from backtest.engine import _aggregate_h4

OUT_DIR = ROOT / "experiments"
EXTENDED_PARQUET = ROOT / "data" / "historical" / "GER40_5m_2015-2026.parquet"

DEFAULT_THRESHOLD_DAYS = 7      # min trade-eligible days per 30d window
ROLLING_WINDOW_DAYS = 30


def build_regime_per_day(df: pd.DataFrame) -> dict[dt.date, Regime]:
    """Walk forward, regime per CET date (mirrors backtest engine logic)."""
    daily_history = aggregate_daily(df)
    h4 = _aggregate_h4(df)
    cet_dates = sorted({t.tz_convert("Europe/Berlin").date() for t in df.index})
    regime_by_date: dict[dt.date, Regime] = {}
    raw_history: list[Regime] = []
    active: Regime | None = None
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")
    for d in cet_dates:
        ts_8 = pd.Timestamp(dt.datetime.combine(d, dt.time(8, 0)),
                             tz=cet).tz_convert("UTC").to_pydatetime()
        try:
            sig = derive_signals_from_market_data(daily_history, h4, df, ts_8)
            raw = classify_regime_raw(sig)
        except (ValueError, KeyError):
            raw = Regime.UNDEFINED
        a = get_active_regime(raw_history, raw, current_active=active)
        regime_by_date[d] = a
        raw_history.append(raw)
        active = a
    return regime_by_date


def rolling_eligible_counts(regime_by_date: dict[dt.date, Regime],
                             window_days: int = ROLLING_WINDOW_DAYS) -> pd.DataFrame:
    """For each rolling start date, count non-UNDEFINED days in [start, start+window)."""
    dates = sorted(regime_by_date.keys())
    if not dates:
        return pd.DataFrame()
    rows = []
    for i, d in enumerate(dates):
        end = d + dt.timedelta(days=window_days)
        eligible = sum(1 for j in range(i, len(dates))
                       if dates[j] < end and regime_by_date[dates[j]] != Regime.UNDEFINED)
        rows.append({"window_start": d, "eligible_days": eligible})
    return pd.DataFrame(rows)


def decision(rolling_df: pd.DataFrame, threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> dict:
    """Compute fail %, classify."""
    if rolling_df.empty:
        return {"verdict": "EMPTY", "n_windows": 0}
    n = len(rolling_df)
    fails = (rolling_df["eligible_days"] < threshold_days).sum()
    fail_pct = fails / n * 100
    if fail_pct < 5:
        verdict = "PASS"
    elif fail_pct <= 15:
        verdict = "WARNING"
    else:
        verdict = "REQUIRES ADJUSTMENT"
    return {
        "verdict": verdict,
        "n_windows": int(n),
        "fail_count": int(fails),
        "fail_pct": float(fail_pct),
        "threshold_days": threshold_days,
        "median_eligible": float(rolling_df["eligible_days"].median()),
        "p25": float(rolling_df["eligible_days"].quantile(0.25)),
        "p75": float(rolling_df["eligible_days"].quantile(0.75)),
        "min": int(rolling_df["eligible_days"].min()),
        "max": int(rolling_df["eligible_days"].max()),
    }


def write_html_histogram(rolling_df: pd.DataFrame, out_path: Path) -> None:
    """Simple HTML page with vertical-bar SVG of histogram (no external deps)."""
    bins = list(range(0, 32))  # 0..30 days
    counts = [(rolling_df["eligible_days"] == b).sum() for b in bins]
    max_c = max(counts) or 1
    bar_w = 28
    h = 240
    svg_w = bar_w * len(bins) + 40
    bars = ""
    for i, (b, c) in enumerate(zip(bins, counts)):
        bh = int(h * c / max_c)
        x = 20 + i * bar_w
        y = h - bh + 20
        bars += (f'<rect x="{x}" y="{y}" width="{bar_w-3}" height="{bh}" '
                 f'fill="#3a8" stroke="#234" />'
                 f'<text x="{x+bar_w/2-3}" y="{h+38}" font-size="10" text-anchor="middle">{b}</text>'
                 f'<text x="{x+bar_w/2-3}" y="{y-3}" font-size="9" text-anchor="middle">{c}</text>')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Rolling 30-day eligibility histogram</title></head><body>"
        f"<h2>Rolling 30-day eligibility (n={len(rolling_df)} windows)</h2>"
        f"<p>X = eligible (non-UNDEFINED) days per 30-day window. Y = window count.</p>"
        f"<svg width='{svg_w}' height='{h+60}'>{bars}</svg>"
        f"</body></html>", encoding="utf-8")


def write_decision_md(d: dict, rolling_df: pd.DataFrame, out_path: Path) -> None:
    lines = [
        "# Rolling 30-day Validation — v3.3.2.1 Gate #14 Extension",
        "",
        f"**Verdict:** **{d['verdict']}**",
        "",
        f"- Windows evaluated: {d['n_windows']}",
        f"- Threshold: ≥{d['threshold_days']} non-UNDEFINED days per 30-day window",
        f"- Fail count: {d['fail_count']} ({d['fail_pct']:.2f}%)",
        f"- Median eligible days: {d['median_eligible']:.1f}",
        f"- P25 / P75: {d['p25']:.1f} / {d['p75']:.1f}",
        f"- Min / Max: {d['min']} / {d['max']}",
        "",
        "## Decision tree (Pavel spec)",
        "- < 5% fail   → PASS",
        "- 5-15% fail  → WARNING",
        "- > 15% fail  → REQUIRES ADJUSTMENT",
        "",
        "## Sample of failed windows",
        "",
    ]
    fails = rolling_df[rolling_df["eligible_days"] < d["threshold_days"]].head(20)
    if not fails.empty:
        lines.append("| window_start | eligible_days |")
        lines.append("|---|---:|")
        for _, row in fails.iterrows():
            lines.append(f"| {row['window_start']} | {row['eligible_days']} |")
    else:
        lines.append("(no failed windows)")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", type=Path, default=EXTENDED_PARQUET)
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_DAYS)
    p.add_argument("--window", type=int, default=ROLLING_WINDOW_DAYS)
    a = p.parse_args()
    if not a.parquet.exists():
        print(f"parquet not found: {a.parquet}", file=sys.stderr)
        return 1
    print(f"[rolling] loading {a.parquet}")
    feed = BarFeed.from_parquet(a.parquet)
    df = feed.to_dataframe()
    print(f"[rolling] building regime per day for {len(df)} bars")
    regime_by_date = build_regime_per_day(df)
    print(f"[rolling] {len(regime_by_date)} CET dates classified")
    rolling = rolling_eligible_counts(regime_by_date, window_days=a.window)
    print(f"[rolling] {len(rolling)} rolling windows computed")
    d = decision(rolling, threshold_days=a.threshold)
    print(f"[rolling] verdict: {d['verdict']} (fail_pct={d['fail_pct']:.2f}%)")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_html_histogram(rolling, OUT_DIR / "rolling_30day_histogram.html")
    write_decision_md(d, rolling, OUT_DIR / "rolling_30day_decision.md")
    print(f"[rolling] outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
