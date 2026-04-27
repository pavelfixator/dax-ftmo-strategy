"""ORB-DAX v3.3.1 — regime-aware Trend Open Range Breakout.

Spec: Strategy v3.3.1 §2.4 + Pavel hybrid plan + adversarial 9-kol design.

Key differences vs v3.2 (orb_dax.py — DEPRECATED):
  - regime parametr: TREND / CALM / CRASH / UNDEFINED
  - filter sets per regime (defaults pre-ablation):
      TREND: F1 + F2 + F3 + F4
      CALM:  F1 + F2 + F3 + F4
      CRASH: F1 MANDATORY + F2 + F5_CRASH placeholder
  - F5_CRASH default: F5a Connors-Raschke range expansion
      (5m bar |H-L| > 2× ATR(14) 5m). To be replaced by Exp #12 winner.
  - UNDEFINED → return None (no trade)

Filtry (definice):
  F1 Daily Bias  — 3 booleans all-true (yest_close vs EMA20D1, vs yest_open, vs day_before_close)
  F2 ORB15       — high/low prvních 3 × 5m barů 09:00-09:15 CET, range >= 10 pts
  F3 Volume      — bar volume > 1.5× avg volume prvních 3 ORB barů
  F4 ATR rel     — ATR(14) 5m at 09:00-09:15 > 0.7× rolling 20-day median
  F5_CRASH (a)   — current bar |high - low| > 2.0× ATR(14) 5m (range expansion)

Entry / SL / TP (stejné jako v3.2):
  Entry: 5m close baru breakout above ORB high (LONG) / below ORB low (SHORT)
  SL_raw = max(35 pts, 1.5 × ATR(14) 5m)  →  SL_eff = SL_raw + 3.5 (spread+slip)
  TP1   = 2 × ORB range (RRR 1:2), scale-out 50 % handled by engine
  Time window entry: 09:15-10:00 CET
"""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

import pandas as pd

from src.strategy.indicators import atr
from src.strategy.regime import Regime
from .base_setup import BaseSetup, Signal
from .orb_dax import (
    compute_orb, daily_bias, f4_atr_relative, _to_cet_time, _to_cet_date,
    ENTRY_WINDOW_START, ENTRY_WINDOW_END,
    SL_MIN_POINTS, SL_ATR_MULT, SLIPPAGE_AND_SPREAD_POINTS, RRR_TARGET,
    VOLUME_THRESHOLD,
)

# F5_CRASH default — Connors-Raschke range expansion
F5A_RANGE_EXPANSION_MULT = 2.0


def f5_crash_range_expansion(bar: pd.Series, atr5: float) -> bool:
    """F5a: 5m bar |H-L| > 2× ATR(14) 5m (Connors-Raschke range expansion)."""
    if atr5 is None or atr5 <= 0:
        return False
    return float(bar["high"] - bar["low"]) > F5A_RANGE_EXPANSION_MULT * atr5


REGIME_FILTERS: dict[Regime, set] = {
    Regime.TREND:     {"F1", "F2", "F3", "F4"},
    Regime.CALM:      {"F1", "F2", "F3", "F4"},
    Regime.CRASH:     {"F1", "F2", "F5_CRASH"},  # F1 + F2 mandatory, F5_CRASH replaces F3+F4
    Regime.UNDEFINED: set(),
}


class OrbDaxSetupV331(BaseSetup):
    """ORB-DAX v3.3.1 — regime-aware filter selection."""

    name = "orb_dax_v331"
    setup_type = "A"

    def __init__(self):
        # filter set is regime-determined; keep setup_type="A" for sizing lookup
        pass

    def check_entry(self, market_data) -> Optional[Signal]:
        raise NotImplementedError("Use check_entry_at(session_5m, daily_df, ts, regime)")

    def get_sl(self, entry: float, direction: str, market_data=None) -> float:
        a5 = (market_data or {}).get("atr5_at_entry") if isinstance(market_data, dict) else None
        sl_raw = max(SL_MIN_POINTS, SL_ATR_MULT * (a5 or 0))
        offset = sl_raw + SLIPPAGE_AND_SPREAD_POINTS
        return entry - offset if direction == "LONG" else entry + offset

    def get_tp(self, entry: float, sl: float, direction: str,
               orb_range: Optional[float] = None) -> float:
        if orb_range:
            target = 2 * orb_range
            return entry + target if direction == "LONG" else entry - target
        risk = abs(entry - sl)
        return entry + RRR_TARGET * risk if direction == "LONG" else entry - RRR_TARGET * risk

    def check_entry_at(self, session_5m: pd.DataFrame, daily_df: pd.DataFrame,
                       ts: pd.Timestamp, regime: Regime,
                       *, history_5m: Optional[pd.DataFrame] = None) -> Optional[Signal]:
        """Vyhodnocení 1 baru s regime-aware filtry.

        Args:
            session_5m: bary aktuálního CET dne až po `ts`.
            daily_df:   D1 OHLC starší než dnešek (EMA20 + bias).
            ts:         timestamp aktuálního 5m baru (UTC).
            regime:     dnešní active Regime (z classifier + persistence).
            history_5m: ≥20 dní 5m pro F4 ATR baseline.

        Returns:
            Signal pokud projdou regime-specific filtry, jinak None.
            UNDEFINED regime → vždy None.
        """
        if regime == Regime.UNDEFINED:
            return None
        active_filters = REGIME_FILTERS[regime]
        if ts not in session_5m.index:
            return None
        if not (ENTRY_WINDOW_START <= _to_cet_time(ts) < ENTRY_WINDOW_END):
            return None

        bars_up_to = session_5m.loc[:ts]
        # F2 ORB15 — required for entry direction calculation in all regimes
        orb = compute_orb(bars_up_to)
        if orb is None:
            return None

        today_date = _to_cet_date(ts)
        # F1 Daily Bias — MANDATORY in all 3 regimes per v3.3.1
        bull, bear = daily_bias(daily_df, today_date)
        if not (bull or bear):
            return None

        bar = bars_up_to.iloc[-1]
        close = float(bar["close"])
        if bull and close > orb.orb_high:
            direction = "LONG"
        elif bear and close < orb.orb_low:
            direction = "SHORT"
        else:
            return None

        filters_met = 2  # F1 + F2 confirmed
        filters_total = len(active_filters)

        # F3 Volume confirm
        if "F3" in active_filters:
            if float(bar["volume"]) < VOLUME_THRESHOLD * orb.orb_avg_volume:
                return None
            filters_met += 1

        # F4 ATR relative
        if "F4" in active_filters:
            f4 = f4_atr_relative(history_5m, today_date) if history_5m is not None else None
            if f4 is False:
                return None
            if f4 is True:
                filters_met += 1
            # If f4 is None (insufficient history) → don't block, don't count

        # F5_CRASH range expansion
        a5_series = atr(bars_up_to, 14).dropna()
        a5 = float(a5_series.iloc[-1]) if not a5_series.empty else None
        if "F5_CRASH" in active_filters:
            if not f5_crash_range_expansion(bar, a5):
                return None
            filters_met += 1

        entry = close
        sl = self.get_sl(entry, direction, {"atr5_at_entry": a5})
        tp = self.get_tp(entry, sl, direction, orb_range=orb.orb_range)
        return Signal(
            setup_name=f"{self.name}_{regime.value.lower()}",
            direction=direction,
            entry=entry, sl=sl, tp=tp,
            lots=0.0, risk_usd=0.0,
            confidence=filters_met / max(filters_total, 1),
            filters_met=filters_met,
            filters_total=filters_total,
        )
