"""Historical OHLC data downloader — Dukascopy free fallback.

Default zdroj: **Dukascopy** veřejný tick feed (žádné credentials, žádné rate limity
v rozumných mezích). Ticks po hodinách → LZMA dekomprese → resample na požadovaný
timeframe → parquet.

  python scripts/download_data.py --symbol DEUIDXEUR \
      --start 2024-01-01 --end 2026-04-25 --tf M15 \
      --out data/GER40_M15_2024-2026.parquet

Důležité poznámky pro DAX FTMO Phase 0:
  - Dukascopy `DEUIDXEUR` = cash DAX index (Xetra hodiny). NENÍ to FTMO `GER40.cash`
    CFD, ale tick-level prices odpovídají s rozdílem spread/markup. Pro pattern
    research a indikátory dostatečné; pro slippage/spread modeling kalibrovat
    proti MT5 historii (`MetaTrader5.copy_rates_range`) — to je úkol Phase 1.
  - Dukascopy posílá sobotní/nedělní hodiny jako 0-byte response (HTTP 200) →
    skipujeme bez chyby.
  - Tick formát: 20 B/tick, big-endian, 5 polí
      uint32 ms_offset_from_hour
      uint32 ask_price (× 10^point_factor)
      uint32 bid_price (× 10^point_factor)
      float32 ask_volume
      float32 bid_volume
    `point_factor` pro DAX index = 3 (price * 1000 → integer).
  - URL pattern používá MĚSÍC INDEX 0-11 (leden=00). Pozor.

Cache: bi5 soubory se ukládají do `data/dukascopy_cache/<SYMBOL>/<YYYY>/<MM>/<DD>/<HH>h.bi5`
takže opakovaný běh nestahuje znovu.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import lzma
import struct
import sys
import time
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
import requests

DUKASCOPY_BASE = "https://datafeed.dukascopy.com/datafeed"
TICK_STRUCT = struct.Struct(">IIIff")  # 20 B
DEFAULT_POINT_FACTOR = {
    "DEUIDXEUR": 3,
    "USA500IDXUSD": 3,
    "USATECHIDXUSD": 3,
    "USA30IDXUSD": 3,
    "EURUSD": 5,
}
TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H4": "4h", "D1": "1D",
}
USER_AGENT = "dax-ftmo-bot/0.2 (+research)"


def _http_get(url: str, *, timeout: float = 30.0, retries: int = 3) -> bytes | None:
    """Returns raw bytes on 200, None on 404 / empty, raises on persistent failure."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content if r.content else None
        except requests.RequestException as e:
            last_exc = e
            time.sleep(1.5 ** attempt)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} ({last_exc})")


def _bi5_url(symbol: str, ts: dt.datetime) -> str:
    # Dukascopy month index is 0-based.
    return (f"{DUKASCOPY_BASE}/{symbol}/{ts.year:04d}/{ts.month - 1:02d}/"
            f"{ts.day:02d}/{ts.hour:02d}h_ticks.bi5")


def _cache_path(cache_dir: Path, symbol: str, ts: dt.datetime) -> Path:
    return (cache_dir / symbol / f"{ts.year:04d}" / f"{ts.month:02d}"
            / f"{ts.day:02d}" / f"{ts.hour:02d}h.bi5")


def _fetch_hour(symbol: str, ts: dt.datetime, cache_dir: Path) -> bytes | None:
    cp = _cache_path(cache_dir, symbol, ts)
    if cp.exists():
        return cp.read_bytes() or None
    blob = _http_get(_bi5_url(symbol, ts))
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_bytes(blob if blob is not None else b"")
    return blob


def _parse_ticks(blob: bytes, hour_ts: dt.datetime, point_factor: int) -> pd.DataFrame:
    if not blob:
        return pd.DataFrame()
    try:
        raw = lzma.decompress(blob)
    except lzma.LZMAError:
        return pd.DataFrame()
    n = len(raw) // 20
    if n == 0:
        return pd.DataFrame()
    arr = np.frombuffer(raw[:n * 20], dtype=">u4,>u4,>u4,>f4,>f4")
    divisor = 10 ** point_factor
    base_ms = int(hour_ts.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    times = pd.to_datetime(base_ms + arr["f0"].astype(np.int64), unit="ms", utc=True)
    df = pd.DataFrame({
        "ts": times,
        "ask": arr["f1"].astype(np.float64) / divisor,
        "bid": arr["f2"].astype(np.float64) / divisor,
        "ask_vol": arr["f3"].astype(np.float64),
        "bid_vol": arr["f4"].astype(np.float64),
    })
    df["mid"] = (df["ask"] + df["bid"]) / 2.0
    return df.set_index("ts")


def _resample(ticks: pd.DataFrame, rule: str) -> pd.DataFrame:
    if ticks.empty:
        return ticks
    o = ticks["mid"].resample(rule).ohlc()
    v = (ticks["ask_vol"] + ticks["bid_vol"]).resample(rule).sum()
    o["volume"] = v
    return o.dropna(subset=["open"])


def _hours_in_range(start: dt.datetime, end: dt.datetime) -> Iterator[dt.datetime]:
    cur = start.replace(minute=0, second=0, microsecond=0, tzinfo=dt.timezone.utc)
    end_utc = end.replace(tzinfo=dt.timezone.utc)
    step = dt.timedelta(hours=1)
    while cur < end_utc:
        # Skip weekends (Sat=5, Sun=6) — Dukascopy has no data, saves HTTP round trips.
        if cur.weekday() < 5:
            yield cur
        cur += step


def download(symbol: str, start: dt.datetime, end: dt.datetime, tf: str,
             out_path: Path, cache_dir: Path, point_factor: int,
             progress_every: int = 24) -> dict:
    if tf not in TF_MAP:
        raise ValueError(f"unsupported tf={tf}; choose from {sorted(TF_MAP)}")
    rule = TF_MAP[tf]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    bars: list[pd.DataFrame] = []
    hours = list(_hours_in_range(start, end))
    n_total = len(hours)
    n_with_data = 0
    n_empty = 0
    n_404 = 0
    t0 = time.time()
    for idx, h in enumerate(hours, 1):
        try:
            blob = _fetch_hour(symbol, h, cache_dir)
        except Exception as e:
            print(f"  WARN {h.isoformat()}: {e}", file=sys.stderr)
            blob = None
        if blob is None:
            n_404 += 1
        else:
            ticks = _parse_ticks(blob, h, point_factor)
            if ticks.empty:
                n_empty += 1
            else:
                n_with_data += 1
                bars.append(_resample(ticks, rule))
        if idx % progress_every == 0 or idx == n_total:
            elapsed = time.time() - t0
            rate = idx / max(elapsed, 0.001)
            eta = (n_total - idx) / max(rate, 0.001)
            print(f"  [{idx}/{n_total}] {h.date()} h{h.hour:02d} | "
                  f"data={n_with_data} empty={n_empty} 404={n_404} | "
                  f"rate={rate:.1f}/s eta={eta:.0f}s")

    if not bars:
        raise RuntimeError("no data downloaded — check symbol / date range")
    df = pd.concat(bars, axis=0).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = "ts_utc"

    if out_path.suffix == ".parquet":
        df.to_parquet(out_path, compression="zstd")
    elif out_path.suffix == ".csv":
        df.to_csv(out_path)
    elif out_path.name.endswith(".csv.gz"):
        df.to_csv(out_path, compression="gzip")
    else:
        raise ValueError(f"unsupported output suffix: {out_path.suffix}")

    return {
        "rows": int(len(df)),
        "first": df.index.min().isoformat(),
        "last": df.index.max().isoformat(),
        "out": str(out_path),
        "hours_total": n_total,
        "hours_with_data": n_with_data,
        "hours_empty": n_empty,
        "hours_404": n_404,
    }


def _parse_date(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d")


def main() -> int:
    p = argparse.ArgumentParser(description="Dukascopy free-tier OHLC downloader.")
    p.add_argument("--symbol", default="DEUIDXEUR",
                   help="Dukascopy symbol (default: DEUIDXEUR = DAX cash)")
    p.add_argument("--start", required=True, type=_parse_date, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end", required=True, type=_parse_date, help="YYYY-MM-DD (exclusive)")
    p.add_argument("--tf", default="M15", choices=sorted(TF_MAP), help="output timeframe")
    p.add_argument("--out", required=True, type=Path, help="output file (.parquet | .csv | .csv.gz)")
    p.add_argument("--cache-dir", type=Path,
                   default=Path("C:/Users/AOS Server/dax-ftmo-bot/data/dukascopy_cache"))
    p.add_argument("--point-factor", type=int, default=None,
                   help="price decimal shift; auto-detected from symbol if omitted")
    a = p.parse_args()

    pf = a.point_factor if a.point_factor is not None else DEFAULT_POINT_FACTOR.get(a.symbol)
    if pf is None:
        print(f"ERROR: unknown symbol {a.symbol}, pass --point-factor explicitly", file=sys.stderr)
        return 2
    print(f"[download_data] symbol={a.symbol} pf={pf} tf={a.tf} "
          f"range={a.start.date()}..{a.end.date()} -> {a.out}")
    res = download(a.symbol, a.start, a.end, a.tf, a.out, a.cache_dir, pf)
    print("\n[done]", res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
