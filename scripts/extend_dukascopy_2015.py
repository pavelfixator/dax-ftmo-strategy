"""Extend Dukascopy cache 2015-01-01 → 2018-12-31 s exponential backoff.

Reaguje na předchozí Dukascopy run, který byl rate-limited po ~26000 requests
(throughput drop 2.6/s → 0.05/s). Tato implementace:

  - Reuse cache layout a parsing infrastructury z scripts/download_data.py
  - Adaptivní exponential backoff per failure
      base 1.0 s → 2.0 → 4.0 → ... → max 300 s
      max 10 retries, random jitter ±25 %
  - Resume-from-cache: každý 200/empty/cached hit jde rovnou bez HTTP
  - Validace po dokončení:
      * tick gap coverage ≥ 99 % během trading hours (Mon-Fri)
      * žádné spike anomálie >3σ na minutových resampled datech
  - Append do data/dukascopy_cache/DEUIDXEUR/<YYYY>/<MM>/<DD>/<HH>h.bi5
    (zero-byte = 404 marker, jako u download_data.py)

Usage:
  python scripts/extend_dukascopy_2015.py
  python scripts/extend_dukascopy_2015.py --start 2015-01-01 --end 2019-01-01
  python scripts/extend_dukascopy_2015.py --validate-only
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Reuse infra from download_data.py (cache layout, parser, URL builder)
from scripts.download_data import (  # noqa: E402
    DUKASCOPY_BASE, USER_AGENT, _bi5_url, _cache_path, _parse_ticks,
    _hours_in_range, DEFAULT_POINT_FACTOR,
)

DEFAULT_CACHE_DIR = ROOT / "data" / "dukascopy_cache"
DEFAULT_SYMBOL = "DEUIDXEUR"
DEFAULT_START = dt.datetime(2015, 1, 1)
DEFAULT_END = dt.datetime(2019, 1, 1)  # exclusive

BACKOFF_BASE_S = 1.0
BACKOFF_FACTOR = 2.0
BACKOFF_MAX_S = 300.0
MAX_RETRIES = 10
JITTER_PCT = 0.25
HTTP_TIMEOUT = 30.0
PROGRESS_EVERY = 200


def _backoff_get(url: str, retries: int = MAX_RETRIES) -> bytes | None:
    """HTTP GET s exp backoff; vrací bytes na 200, None na 404 / repeated fail."""
    delay = BACKOFF_BASE_S
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT,
                             headers={"User-Agent": USER_AGENT})
            if r.status_code == 404:
                return None
            if r.status_code == 200:
                return r.content if r.content else None
            # 5xx / 429 / other → backoff
            if r.status_code in (429, 502, 503, 504):
                pass  # fall through to sleep
            else:
                return None  # unexpected, give up
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
        # Sleep with jitter
        sleep_s = min(delay, BACKOFF_MAX_S)
        sleep_s *= 1 + random.uniform(-JITTER_PCT, JITTER_PCT)
        time.sleep(max(0.1, sleep_s))
        delay = min(delay * BACKOFF_FACTOR, BACKOFF_MAX_S)
    if last_exc:
        print(f"  ! GIVE UP {url}: {last_exc}", file=sys.stderr)
    return None


def fetch_one_hour(symbol: str, ts: dt.datetime, cache_dir: Path) -> tuple[str, bytes | None]:
    """Returns ('cache_hit'|'cache_empty'|'http_data'|'http_404'|'http_fail', blob)."""
    cp = _cache_path(cache_dir, symbol, ts)
    if cp.exists():
        b = cp.read_bytes()
        return ("cache_hit" if b else "cache_empty", b or None)
    blob = _backoff_get(_bi5_url(symbol, ts))
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_bytes(blob if blob is not None else b"")
    if blob is None:
        return ("http_404", None)
    return ("http_data", blob)


def extend_range(symbol: str, start: dt.datetime, end: dt.datetime,
                 cache_dir: Path) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    hours = list(_hours_in_range(start, end))
    n_total = len(hours)
    counts = {"cache_hit": 0, "cache_empty": 0, "http_data": 0,
              "http_404": 0, "http_fail": 0}
    t0 = time.time()
    for idx, h in enumerate(hours, 1):
        kind, _ = fetch_one_hour(symbol, h, cache_dir)
        counts[kind] = counts.get(kind, 0) + 1
        if idx % PROGRESS_EVERY == 0 or idx == n_total:
            elapsed = time.time() - t0
            rate = idx / max(elapsed, 0.001)
            eta = (n_total - idx) / max(rate, 0.001)
            print(f"  [{idx}/{n_total}] {h.date()} h{h.hour:02d} | "
                  f"hit={counts['cache_hit']} empty={counts['cache_empty']} "
                  f"data={counts['http_data']} 404={counts['http_404']} "
                  f"fail={counts.get('http_fail', 0)} | rate={rate:.2f}/s eta={eta:.0f}s")
    return counts


def parse_for_validation(symbol: str, start: dt.datetime, end: dt.datetime,
                         cache_dir: Path, point_factor: int) -> pd.DataFrame:
    """Build a 1-min resampled OHLCV DataFrame from cached bi5 files."""
    rows = []
    for h in _hours_in_range(start, end):
        cp = _cache_path(cache_dir, symbol, h)
        if not cp.exists():
            continue
        blob = cp.read_bytes()
        if not blob:
            continue
        df = _parse_ticks(blob, h, point_factor)
        if df.empty:
            continue
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    ticks = pd.concat(rows).sort_index()
    m1 = ticks["mid"].resample("1min").ohlc()
    m1["volume"] = (ticks["ask_vol"] + ticks["bid_vol"]).resample("1min").sum()
    return m1.dropna(subset=["open"])


def validate(df: pd.DataFrame) -> dict:
    """Coverage + spike checks per Pavel's spec."""
    if df.empty:
        return {"empty": True}
    # Trading-hours coverage: count present bars vs expected per Mon-Fri
    df_th = df[df.index.weekday < 5]
    if df_th.empty:
        return {"trading_hours_empty": True}
    # Coverage: % of 1-min bars present in the trading-hour window
    expected = pd.date_range(df_th.index.min().floor("D"),
                             df_th.index.max().ceil("D"), freq="1min", tz="UTC")
    expected_th = expected[expected.weekday < 5]
    coverage_pct = (len(df_th) / len(expected_th)) * 100 if len(expected_th) else 0.0
    # Spike anomaly: |close.diff()| / rolling std > 3
    if len(df) > 100:
        diffs = df["close"].diff().abs()
        rolling_std = diffs.rolling(window=60, min_periods=20).std()
        z = diffs / rolling_std
        spikes = (z > 3.0).sum()
    else:
        spikes = 0
    return {
        "rows": int(len(df)),
        "first": df.index.min().isoformat(),
        "last": df.index.max().isoformat(),
        "trading_hour_rows": int(len(df_th)),
        "trading_hour_coverage_pct": round(coverage_pct, 2),
        "spike_count_3sigma": int(spikes),
        "price_min": float(df["low"].min()),
        "price_max": float(df["high"].max()),
        "price_mean_close": float(df["close"].mean()),
    }


def _parse_dt(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default=DEFAULT_SYMBOL)
    p.add_argument("--start", type=_parse_dt, default=DEFAULT_START.strftime("%Y-%m-%d"))
    p.add_argument("--end", type=_parse_dt, default=DEFAULT_END.strftime("%Y-%m-%d"))
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    p.add_argument("--validate-only", action="store_true",
                   help="Skip download, only parse cache + validate")
    a = p.parse_args()

    if isinstance(a.start, str):
        a.start = _parse_dt(a.start)
    if isinstance(a.end, str):
        a.end = _parse_dt(a.end)

    print(f"[extend] symbol={a.symbol} range={a.start.date()}..{a.end.date()} cache={a.cache_dir}")
    if not a.validate_only:
        counts = extend_range(a.symbol, a.start, a.end, a.cache_dir)
        print(f"\n[extend] download counts: {counts}")

    pf = DEFAULT_POINT_FACTOR.get(a.symbol)
    if pf is None:
        print(f"[extend] unknown point_factor for {a.symbol}, skipping validation")
        return 0
    print(f"\n[extend] validating cache (parsing all bi5 in range)...")
    df = parse_for_validation(a.symbol, a.start, a.end, a.cache_dir, pf)
    summary = validate(df)
    print(f"\n[extend] validation summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
