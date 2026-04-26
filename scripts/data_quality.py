"""Data quality checks pro stažený OHLC parquet — gaps, spikes, DST.

Usage:
  python scripts/data_quality.py --in data/historical/GER40_5m_2019-2026.parquet
  python scripts/data_quality.py --in <file> --report data/historical/GER40_5m_qa.json

Reportuje:
  - Coverage: total bars, range, # trading days
  - Gaps: missing bars > N*expected_freq (vyloučeny weekends a ECB/Christmas holidays)
  - Spikes: abs(close-close) > threshold (default: 5% denní)
  - DST transitions: bars sedí na CET/CEST switch (3rd Sunday of March/October)
  - Volume zeros / NaNs

Bez fail/pass policy — pouze surface anomálie pro lidský review.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TF_MINUTES = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "1h": 60}


def _infer_freq_minutes(df: pd.DataFrame) -> int:
    diffs = df.index.to_series().diff().dropna().dt.total_seconds() / 60
    if diffs.empty:
        return 5
    # mode of intra-day diffs (skip weekend-sized gaps)
    mode = diffs[diffs < 240].mode()
    return int(mode.iloc[0]) if not mode.empty else int(diffs.median())


def _is_trading_minute(ts: pd.Timestamp) -> bool:
    """Mon-Fri 22:00 UTC Sun .. 21:00 UTC Fri (Dukascopy convention).

    Cash DAX má užší okno (Xetra 07:00-15:30 UTC), ale Dukascopy serves data
    i mimo Xetra (CFD-style). Pro gap detection bereme broader window.
    """
    return ts.weekday() < 5  # Mon-Fri


def gaps(df: pd.DataFrame, expected_freq_min: int) -> pd.DataFrame:
    diffs = df.index.to_series().diff().dt.total_seconds() / 60
    threshold = expected_freq_min * 2.5  # tolerance for tick-based resampling
    rows = []
    for ts, gap in diffs.items():
        if pd.isna(gap) or gap <= threshold:
            continue
        prev = ts - pd.Timedelta(minutes=gap)
        if prev.weekday() == 4 and ts.weekday() == 0:
            continue  # weekend
        rows.append({"prev_bar": prev, "next_bar": ts, "gap_min": int(gap)})
    return pd.DataFrame(rows).sort_values("gap_min", ascending=False) if rows else pd.DataFrame()


def spikes(df: pd.DataFrame, pct_threshold: float = 0.05) -> pd.DataFrame:
    ret = df["close"].pct_change().abs()
    big = ret[ret > pct_threshold]
    rows = [{"ts": ts, "pct_move": float(r), "close": float(df.loc[ts, "close"])}
            for ts, r in big.items()]
    return pd.DataFrame(rows).sort_values("pct_move", ascending=False) if rows else pd.DataFrame()


def dst_transitions(df: pd.DataFrame) -> list[dict]:
    """3rd Sunday March (CET→CEST) + last Sunday October (CEST→CET).

    Pro každou DST hranici v rozsahu df ověříme, že kolem ní existují bary.
    """
    years = sorted({df.index.min().year + i for i in range(df.index.max().year - df.index.min().year + 1)})
    events = []
    for y in years:
        # 3rd Sunday March (EU spring forward 01:00→02:00 UTC, 02:00→03:00 CET)
        d = dt.date(y, 3, 1)
        while d.weekday() != 6:
            d += dt.timedelta(days=1)
        d += dt.timedelta(days=14)
        events.append({"year": y, "kind": "spring", "date": d.isoformat()})
        # Last Sunday October
        d2 = dt.date(y, 10, 31)
        while d2.weekday() != 6:
            d2 -= dt.timedelta(days=1)
        events.append({"year": y, "kind": "autumn", "date": d2.isoformat()})

    out = []
    for ev in events:
        ts_ref = pd.Timestamp(ev["date"]).tz_localize("UTC")
        if ts_ref < df.index.min() or ts_ref > df.index.max():
            continue
        window = df.loc[(df.index >= ts_ref) & (df.index < ts_ref + pd.Timedelta(hours=24))]
        out.append({**ev, "bars_in_24h": int(len(window))})
    return out


def report(parquet_in: Path) -> dict:
    df = pd.read_parquet(parquet_in)
    if df.empty:
        return {"error": "empty parquet", "path": str(parquet_in)}
    df = df.sort_index()

    freq = _infer_freq_minutes(df)
    g = gaps(df, freq)
    sp = spikes(df, pct_threshold=0.03)  # 3 % per bar = strong move
    dst = dst_transitions(df)

    out = {
        "path": str(parquet_in),
        "rows": int(len(df)),
        "first": df.index.min().isoformat(),
        "last": df.index.max().isoformat(),
        "inferred_freq_min": freq,
        "trading_days": int(df.index.normalize().nunique()),
        "gaps": {
            "count": int(len(g)),
            "max_gap_min": int(g["gap_min"].max()) if not g.empty else 0,
            "top_5": g.head(5).to_dict("records") if not g.empty else [],
        },
        "spikes_3pct": {
            "count": int(len(sp)),
            "max_pct": float(sp["pct_move"].max()) if not sp.empty else 0.0,
            "top_5": [
                {"ts": str(r["ts"]), "pct_move": r["pct_move"], "close": r["close"]}
                for r in (sp.head(5).to_dict("records") if not sp.empty else [])
            ],
        },
        "dst_transitions": dst,
        "volume_zeros": int((df["volume"] == 0).sum()),
        "volume_nans": int(df["volume"].isna().sum()),
        "ohlc_nans": int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum()),
        "price_range": {
            "min": float(df["low"].min()),
            "max": float(df["high"].max()),
            "mean_close": float(df["close"].mean()),
        },
    }
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True, type=Path)
    p.add_argument("--report", type=Path, default=None,
                   help="optional JSON output path; default = stdout only")
    a = p.parse_args()
    r = report(a.inp)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
        print(f"[data_quality] report -> {a.report}")
    print(json.dumps(r, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
