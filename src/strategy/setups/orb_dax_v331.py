"""ORB-DAX v3.3.2.1 — CALM-only Trend Open Range Breakout.

Spec: Strategy v3.3.2.1 (post adversarial 12-round design + ablation).

CALM-only scope (data-driven post Sekce 5):
  - Extended ablation 11 yrs / 44 cells: ORB-DAX TREND baseline = 7 trades, 0% WR
    (dead setup). ORB-DAX CRASH = 0/10 PRIMARY cells (insufficient sample).
  - Only ORB-DAX CALM drop_F3 winner: 122 trades, 34% WR, +18.8 exp,
    Sharpe 3.6, FDR sig, OOS pass.
  - v3.3.2.1: ORB-DAX active ONLY in CALM regime, default config = drop_F3
    (filters F1 + F2 + F4, F3 volume removed).

Filtry (CALM only):
  F1 Daily Bias  — 3 booleans all-true (yest_close vs EMA20D1, vs yest_open, vs day_before_close)
  F2 ORB15       — high/low prvních 3 × 5m barů 09:00-09:15 CET, range >= 10 pts
  F4 ATR rel     — ATR(14) 5m at 09:00-09:15 > 0.7× rolling 20-day median

DROPPED v3.3.2.1:
  F3 Volume      — drop_F3 winner cell: F3 was binding in CALM (1.5× threshold
                    paralyzed legitimate setupy)
  F5_CRASH       — F5 framework dropped (0/8 candidates passed FDR + OOS)
  TREND regime   — disabled (dead setup)
  CRASH regime   — disabled (insufficient sample)

Entry / SL / TP (unchanged):
  Entry: 5m close breakout above/below ORB
  SL_raw = max(35 pts, 1.5 × ATR(14) 5m)  →  SL_eff = SL_raw + 3.5
  TP1   = 2 × ORB range (RRR 1:2)
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
    Regime.TREND:     set(),                # DISABLED v3.3.2.1
    Regime.CALM:      {"F1", "F2", "F4"},   # drop F3 winner (no volume filter)
    Regime.CRASH:     set(),                # DISABLED v3.3.2.1
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
                       *, history_5m: Optional[pd.DataFrame] = None,
                       skip_filters: Optional[set] = None,
                       f5_override=None) -> Optional[Signal]:
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
        skip = skip_filters or set()
        # v3.3.2.1 regime gate: ORB-DAX active ONLY in CALM
        if regime != Regime.CALM:
            return None
        active_filters = REGIME_FILTERS[regime]
        if ts not in session_5m.index:
            return None
        if not (ENTRY_WINDOW_START <= _to_cet_time(ts) < ENTRY_WINDOW_END):
            return None

        bars_up_to = session_5m.loc[:ts]
        # F2 ORB15 — required for entry direction calculation in all regimes
        orb = compute_orb(bars_up_to)
        if orb is None and "F2" not in skip:
            return None
        if orb is None:
            return None  # need ORB for breakout direction even when F2 skipped

        today_date = _to_cet_date(ts)
        # F1 Daily Bias
        if "F1" in skip:
            bull = bear = False
            bias_known = False
        else:
            bull, bear = daily_bias(daily_df, today_date)
            bias_known = True
            if not (bull or bear):
                return None

        bar = bars_up_to.iloc[-1]
        close = float(bar["close"])
        if bias_known:
            if bull and close > orb.orb_high:
                direction = "LONG"
            elif bear and close < orb.orb_low:
                direction = "SHORT"
            else:
                return None
        else:
            if close > orb.orb_high:
                direction = "LONG"
            elif close < orb.orb_low:
                direction = "SHORT"
            else:
                return None

        filters_met = 2 if bias_known else 1
        filters_total = len(active_filters)

        # F3 Volume confirm — DROPPED v3.3.2.1 (drop_F3 was winner)
        # Block kept only when caller explicitly re-enables via custom skip semantics.
        if "F3" in active_filters and "F3" not in skip:
            if float(bar["volume"]) < VOLUME_THRESHOLD * orb.orb_avg_volume:
                return None
            filters_met += 1

        # F4 ATR relative
        if "F4" in active_filters and "F4" not in skip:
            f4 = f4_atr_relative(history_5m, today_date) if history_5m is not None else None
            if f4 is False:
                return None
            if f4 is True:
                filters_met += 1
            # If f4 is None (insufficient history) → don't block, don't count

        # ATR for SL — keep computation (needed for SL even without F5_CRASH)
        a5_series = atr(bars_up_to, 14).dropna()
        a5 = float(a5_series.iloc[-1]) if not a5_series.empty else None
        # F5_CRASH framework DROPPED v3.3.2.1 (0/4 candidates passed FDR/OOS).
        # CRASH regime is disabled, so this branch is unreachable; kept stub
        # for ablation backward-compat (ignored if F5_CRASH not in active set).

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
