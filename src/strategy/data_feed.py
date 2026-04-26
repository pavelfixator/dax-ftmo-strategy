"""Replay-mode OHLC data feed pro backtest a paper-trading.

Načítá parquet (`data/historical/...`) a poskytuje:
  - `load(path, ...)` → pd.DataFrame s tz-aware DatetimeIndex (UTC)
  - `BarFeed.iter_bars()` — generator (ts_utc, ts_cet, bar_dict)
  - `BarFeed.range(...)` — sub-feed pro konkrétní okno

Konvence:
  - Parquet je generován `scripts/download_data.py` z Dukascopy ticks.
  - Index je tz-aware UTC (`ts_utc` ve sloupci → po `set_index`).
  - Sloupce: open, high, low, close, volume.
  - Resample-aware: tick-based parquet má bar-end timestamps; pro 5m bar
    s časem 09:05 UTC platí, že bar pokrývá 09:00:00..09:04:59 (left-closed).

DST handling: parametry typu `start`/`end` jsou tz-aware (preferred) nebo
naive UTC. Pokud caller předá naive datum + timezone="Europe/Berlin", BarFeed
provede correct DST conversion.

Spec: Strategy v3.2 backtest layer + Trading-Hours.md.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union

import pandas as pd

try:
    from zoneinfo import ZoneInfo  # py3.9+
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

CET = ZoneInfo("Europe/Berlin")
UTC = dt.timezone.utc

REQUIRED_COLS = ("open", "high", "low", "close", "volume")
DateLike = Union[str, dt.date, dt.datetime, pd.Timestamp]


def load(path: Path | str) -> pd.DataFrame:
    """Read parquet, ensure tz-aware UTC index, validate schema."""
    df = pd.read_parquet(path).sort_index()
    if df.empty:
        raise ValueError(f"empty parquet: {path}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"index must be DatetimeIndex, got {type(df.index)}")
    if df.index.tz is None:
        df.index = df.index.tz_localize(UTC)
    elif str(df.index.tz) != "UTC":
        df.index = df.index.tz_convert(UTC)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"parquet missing columns: {missing}")
    return df


def _coerce_to_utc(d: Optional[DateLike], assume_tz: ZoneInfo = CET) -> Optional[pd.Timestamp]:
    if d is None:
        return None
    ts = pd.Timestamp(d)
    if ts.tz is None:
        # Naive → assume CET (Pavel typically writes "2020-01-13" meaning local EU date)
        ts = ts.tz_localize(assume_tz)
    return ts.tz_convert(UTC)


@dataclass
class Bar:
    ts_utc: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def ts_cet(self) -> pd.Timestamp:
        return self.ts_utc.tz_convert(CET)


class BarFeed:
    """Wraps a DataFrame and yields Bar objects in chronological order.

    `BarFeed.range(start, end)` returns a new BarFeed with the same underlying
    dataframe sliced to [start, end). Naive datetimes assume CET wall-clock.
    """

    def __init__(self, df: pd.DataFrame):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("df must be a DataFrame")
        if df.index.tz is None:
            raise ValueError("BarFeed requires tz-aware index (UTC)")
        self.df = df

    @classmethod
    def from_parquet(cls, path: Path | str) -> "BarFeed":
        return cls(load(path))

    def __len__(self) -> int:
        return len(self.df)

    @property
    def first(self) -> pd.Timestamp:
        return self.df.index.min()

    @property
    def last(self) -> pd.Timestamp:
        return self.df.index.max()

    def range(self, start: Optional[DateLike] = None,
              end: Optional[DateLike] = None,
              tz: ZoneInfo = CET) -> "BarFeed":
        s = _coerce_to_utc(start, assume_tz=tz)
        e = _coerce_to_utc(end, assume_tz=tz)
        sliced = self.df
        if s is not None:
            sliced = sliced.loc[sliced.index >= s]
        if e is not None:
            sliced = sliced.loc[sliced.index < e]
        return BarFeed(sliced)

    def trading_session(self, day_cet: DateLike,
                        open_time: dt.time = dt.time(8, 0),
                        close_time: dt.time = dt.time(20, 55)) -> "BarFeed":
        """Slice to one CET trading day [open_time, close_time)."""
        d = pd.Timestamp(day_cet)
        if d.tz is None:
            d = d.tz_localize(CET)
        else:
            d = d.tz_convert(CET)
        start = d.normalize() + pd.Timedelta(hours=open_time.hour, minutes=open_time.minute)
        end = d.normalize() + pd.Timedelta(hours=close_time.hour, minutes=close_time.minute)
        return self.range(start, end, tz=CET)

    def iter_bars(self) -> Iterator[Bar]:
        for ts, row in self.df.iterrows():
            yield Bar(
                ts_utc=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )

    def to_dataframe(self) -> pd.DataFrame:
        return self.df.copy()
