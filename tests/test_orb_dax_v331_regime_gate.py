"""Tests pro v3.3.2.1 ORB-DAX regime gate (CALM-only)."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.regime import Regime
from src.strategy.setups.orb_dax_v331 import (
    OrbDaxSetupV331, REGIME_FILTERS,
)


def _bar(ts_cet, o, h, l, c, v):
    ts = pd.Timestamp(ts_cet, tz="Europe/Berlin").tz_convert("UTC")
    return ts, dict(open=o, high=h, low=l, close=c, volume=v)


def _build(rows):
    idx, data = [], []
    for r in rows:
        ts, b = _bar(*r)
        idx.append(ts); data.append(b)
    return pd.DataFrame(data, index=pd.DatetimeIndex(idx, tz="UTC"))


def _daily(n=25, base=13000.0, bull=True):
    rng = np.random.default_rng(0)
    end = dt.date(2020, 1, 12)
    idx = [end - dt.timedelta(days=i) for i in range(n)][::-1]
    closes = base + np.arange(n) * (5 if bull else -5) + rng.standard_normal(n) * 2
    opens = closes + (-5 if bull else 5)
    return pd.DataFrame({
        "open": opens,
        "high": np.maximum(opens, closes) + 3,
        "low": np.minimum(opens, closes) - 3,
        "close": closes,
        "volume": rng.uniform(1000, 2000, n),
    }, index=pd.to_datetime(idx))


def _session():
    """Build session with 14 warmup bars + ORB + entry candidate."""
    rng = np.random.default_rng(7)
    bars = []
    for i in range(14):
        h = 7 + i // 12
        m = (i % 12) * 5
        c = 13000 + rng.standard_normal() * 2
        bars.append((f"2020-01-13 {h:02d}:{m:02d}", c - 1, c + 3, c - 3, c, 100))
    bars += [
        ("2020-01-13 09:00", 13000, 13010, 12995, 13005, 100),
        ("2020-01-13 09:05", 13005, 13020, 13000, 13015, 100),
        ("2020-01-13 09:10", 13015, 13025, 13010, 13020, 100),
        ("2020-01-13 09:15", 13020, 13035, 13015, 13030, 80),  # low volume — F3 dropped
    ]
    return _build(bars)


class TestRegimeGate:
    """v3.3.2.1: ORB-DAX active ONLY in CALM."""

    @pytest.mark.parametrize("regime", [Regime.TREND, Regime.CRASH, Regime.UNDEFINED])
    def test_non_calm_regimes_return_none(self, regime):
        s = OrbDaxSetupV331()
        df = _session()
        daily = _daily(bull=True)
        ts = df.index[-1]
        assert s.check_entry_at(df, daily, ts, regime) is None

    def test_calm_passes_with_drop_f3_filters(self):
        s = OrbDaxSetupV331()
        df = _session()
        daily = _daily(bull=True)
        ts = df.index[-1]
        sig = s.check_entry_at(df, daily, ts, Regime.CALM)
        assert sig is not None
        assert sig.filters_total == 3  # F1+F2+F4 (no F3)
        assert "calm" in sig.setup_name


class TestFilterMatrix:
    def test_calm_filters_are_f1_f2_f4(self):
        assert REGIME_FILTERS[Regime.CALM] == {"F1", "F2", "F4"}
        assert "F3" not in REGIME_FILTERS[Regime.CALM]
        assert "F5_CRASH" not in REGIME_FILTERS[Regime.CALM]

    def test_trend_and_crash_disabled(self):
        assert REGIME_FILTERS[Regime.TREND] == set()
        assert REGIME_FILTERS[Regime.CRASH] == set()


class TestVolumeNotChecked:
    def test_low_volume_passes_in_calm(self):
        """v3.3.2.1: F3 dropped, low-volume bars must NOT block CALM signal."""
        s = OrbDaxSetupV331()
        df = _session()  # last bar volume = 80 (well below ORB avg 100 × 1.5 = 150)
        daily = _daily(bull=True)
        ts = df.index[-1]
        sig = s.check_entry_at(df, daily, ts, Regime.CALM)
        assert sig is not None  # would have been None pre-v3.3.2.1
