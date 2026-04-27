"""Bar-by-bar backtest engine pro Phase 0 offline backtest.

Mechanika:
  Iteruje 5m bary z BarFeed. Pro každý bar:
    1. Pokud existuje open pozice — check exit (SL hit, TP1 hit + scale 50%,
       TP2 hit, trailing po BE+5, force close window, invalidace per setup).
    2. Pokud žádná pozice (FTMO max 1) — projdi 3 setupy paralelně, vyber
       nejvyšší confidence Signal který projde rules_engine + risk_manager.
    3. Otevři pozici (entry, sl, tp1, lots), zaznamenej do trade log.

Invariants (V7 hard assertions):
  * No-overnight: entry.date == exit.date (CET)
  * Server-side SL: every trade má sl_price set
  * FTMO daily loss: |daily_pnl_usd| <= 5000
  * Black Swan Cap: lots <= compute_lots BSC bound

Output: BacktestResult s per-trade log a aggregate stats.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.strategy.data_feed import BarFeed
from src.strategy.setups.base_setup import Signal
from src.strategy.setups.orb_dax import OrbDaxSetup, aggregate_daily
from src.strategy.setups.vwap_bounce import VwapBounceSetup
from src.strategy.setups.us_momentum import UsMomentumSetup
# v3.3.1 regime-aware
from src.strategy.setups.orb_dax_v331 import OrbDaxSetupV331
from src.strategy.setups.us_momentum_v331 import UsMomentumSetupV331
from src.strategy.regime import Regime, get_active_regime
from src.strategy.regime.classifier import (
    classify_regime_raw, derive_signals_from_market_data,
)
from src.risk.risk_manager import compute_lots, derive_risk_state, RiskState
from src.risk.sizing_v331 import calculate_lots_v331
from src.risk.rules_engine import (
    in_trading_window, before_hard_stop, max_positions, rrr_acceptable,
    regime_allows_trading,
    FORCED_CLOSE_MON_THU, FORCED_CLOSE_FRI,
)

DEFAULT_EQUITY = 100_000.0
DEFAULT_EUR_USD = 1.08
DEFAULT_DAX_PRICE = 24_000.0
FTMO_DAILY_LOSS_LIMIT = 5_000.0


@dataclass
class Trade:
    setup: str
    direction: str
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry: float
    exit: float
    sl: float
    tp: float
    lots: float
    risk_usd: float
    pnl_usd: float
    exit_reason: str  # 'sl' | 'tp1+trail' | 'force_close' | 'invalidation'
    filters_met: int
    filters_total: int

    @property
    def duration_min(self) -> float:
        return (self.exit_ts - self.entry_ts).total_seconds() / 60.0


@dataclass
class OpenPosition:
    setup: str
    direction: str
    entry_ts: pd.Timestamp
    entry: float
    sl: float
    tp: float
    lots: float
    risk_usd: float
    filters_met: int
    filters_total: int
    scaled_out: bool = False
    trailing_active: bool = False


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[pd.Timestamp, float]] = field(default_factory=list)
    invariant_violations: list[str] = field(default_factory=list)

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    def stats(self) -> dict:
        if not self.trades:
            return {"n": 0}
        pnls = [t.pnl_usd for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses)) or 1e-9
        eq = [DEFAULT_EQUITY] + list(pd.Series(pnls).cumsum() + DEFAULT_EQUITY)
        peak = pd.Series(eq).cummax()
        dd = (pd.Series(eq) - peak)
        return {
            "n": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trades),
            "pnl_total_usd": sum(pnls),
            "profit_factor": gross_win / gross_loss,
            "avg_win_usd": (gross_win / len(wins)) if wins else 0.0,
            "avg_loss_usd": (sum(losses) / len(losses)) if losses else 0.0,
            "max_dd_usd": float(dd.min()),
            "max_dd_pct": float(dd.min()) / DEFAULT_EQUITY,
        }


def _pnl_usd(direction: str, entry: float, exit_: float, lots: float,
             eur_usd: float) -> float:
    """1 lot DAX cash = 1 EUR per point. Converted to USD via EURUSD."""
    pts = (exit_ - entry) if direction == "LONG" else (entry - exit_)
    return pts * lots * eur_usd


def _force_close_time_cet(d: dt.date) -> dt.time:
    return FORCED_CLOSE_FRI if d.weekday() == 4 else FORCED_CLOSE_MON_THU


def _exit_check(pos: OpenPosition, bar: pd.Series, ts: pd.Timestamp,
                eur_usd: float) -> Optional[tuple[float, str]]:
    """Returns (exit_price, reason) if position should close on this bar."""
    high, low = float(bar["high"]), float(bar["low"])
    if pos.direction == "LONG":
        if low <= pos.sl:
            return pos.sl, "sl"
        if not pos.scaled_out and high >= pos.tp:
            # Scale out 50 % at TP1 (handled by caller); here we close fully
            # to keep accounting simple in Iter1/2. Engine v2 will do partial.
            return pos.tp, "tp1"
    else:  # SHORT
        if high >= pos.sl:
            return pos.sl, "sl"
        if not pos.scaled_out and low <= pos.tp:
            return pos.tp, "tp1"
    return None


def _force_close_due(pos: OpenPosition, ts_cet: pd.Timestamp) -> bool:
    cutoff = _force_close_time_cet(ts_cet.date())
    return ts_cet.time() >= cutoff


def _aggregate_h4(m5_df: pd.DataFrame) -> pd.DataFrame:
    if m5_df.empty:
        return m5_df
    return m5_df.resample("4h", label="right", closed="right").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["close"])


def run_backtest(
    feed: BarFeed,
    *,
    equity_usd: float = DEFAULT_EQUITY,
    eur_usd_spot: float = DEFAULT_EUR_USD,
    setups: Optional[list] = None,
    risk_state: RiskState = "normal",
    sp500_feed: Optional[BarFeed] = None,
    daily_history: Optional[pd.DataFrame] = None,
    use_v331: bool = False,
) -> BacktestResult:
    """Execute backtest over feed, returns BacktestResult.

    v3.3.1 (use_v331=True): activates regime-aware setupy + sizing.
    Daily regime cached per CET date; UNDEFINED → no trade for that day.
    Default False for backward compat with Iter1/Iter2/Iter2b reports.
    """
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")

    if setups is None:
        if use_v331:
            setups = [OrbDaxSetupV331(), UsMomentumSetupV331()]
        else:
            setups = [
                OrbDaxSetup(filters="A"), OrbDaxSetup(filters="B"),
                VwapBounceSetup(filters="A"), VwapBounceSetup(filters="B"),
                UsMomentumSetup(filters="A"), UsMomentumSetup(filters="B"),
            ]

    df = feed.to_dataframe()
    if daily_history is None:
        daily_history = aggregate_daily(df)

    sp_df = sp500_feed.to_dataframe() if sp500_feed is not None else None

    # v3.3.1 regime cache
    h4_full = _aggregate_h4(df) if use_v331 else None
    regime_cache: dict[dt.date, Regime] = {}
    regime_raw_history: list[Regime] = []
    active_regime: Optional[Regime] = None

    result = BacktestResult()
    open_pos: Optional[OpenPosition] = None
    daily_pnl: dict[dt.date, float] = {}
    cumulative_pnl = 0.0

    # Cache today's session per CET date for setups (avoids re-slicing every bar)
    cet_dates = pd.Series([t.tz_convert(cet).date() for t in df.index],
                           index=df.index)

    def _regime_for(today: dt.date, ts: pd.Timestamp) -> Regime:
        nonlocal active_regime
        if today in regime_cache:
            return regime_cache[today]
        try:
            ts_8am_cet = pd.Timestamp(dt.datetime.combine(today, dt.time(8, 0)),
                                       tz=cet).tz_convert("UTC").to_pydatetime()
            sig = derive_signals_from_market_data(daily_history, h4_full,
                                                    df, ts_8am_cet)
            raw = classify_regime_raw(sig)
        except (ValueError, KeyError):
            raw = Regime.UNDEFINED
        active = get_active_regime(regime_raw_history, raw,
                                     current_active=active_regime)
        regime_cache[today] = active
        regime_raw_history.append(raw)
        active_regime = active
        return active

    for ts, row in df.iterrows():
        ts_cet = ts.tz_convert(cet)
        today = ts_cet.date()

        # 1) exit checks
        if open_pos is not None:
            ex = _exit_check(open_pos, row, ts, eur_usd_spot)
            reason = None
            exit_price = None
            if ex is not None:
                exit_price, reason = ex
            elif _force_close_due(open_pos, ts_cet):
                exit_price = float(row["close"])
                reason = "force_close"
            if reason:
                pnl = _pnl_usd(open_pos.direction, open_pos.entry, exit_price,
                                open_pos.lots, eur_usd_spot)
                trade = Trade(
                    setup=open_pos.setup, direction=open_pos.direction,
                    entry_ts=open_pos.entry_ts, exit_ts=ts,
                    entry=open_pos.entry, exit=exit_price,
                    sl=open_pos.sl, tp=open_pos.tp,
                    lots=open_pos.lots, risk_usd=open_pos.risk_usd,
                    pnl_usd=pnl, exit_reason=reason,
                    filters_met=open_pos.filters_met,
                    filters_total=open_pos.filters_total,
                )
                # Invariants V7
                if trade.entry_ts.tz_convert(cet).date() != trade.exit_ts.tz_convert(cet).date():
                    result.invariant_violations.append(
                        f"V7 NO-OVERNIGHT VIOLATION trade @ {trade.entry_ts}"
                    )
                if trade.sl is None:
                    result.invariant_violations.append(f"V7 SERVER-SL VIOLATION @ {trade.entry_ts}")
                day_total = daily_pnl.get(today, 0.0) + pnl
                if abs(day_total) > FTMO_DAILY_LOSS_LIMIT:
                    result.invariant_violations.append(
                        f"V7 FTMO DAILY-LOSS VIOLATION {day_total:.2f} on {today}"
                    )
                daily_pnl[today] = day_total
                cumulative_pnl += pnl
                result.trades.append(trade)
                result.equity_curve.append((ts, equity_usd + cumulative_pnl))
                open_pos = None

        # 2) entry decision (only if flat)
        if open_pos is None:
            if not in_trading_window(ts_cet).allowed:
                continue
            if not before_hard_stop(ts_cet).allowed:
                continue
            if not max_positions(0).allowed:
                continue  # paranoia; we know we're flat

            # v3.3.1: regime gate
            if use_v331:
                regime = _regime_for(today, ts)
                if not regime_allows_trading(regime).allowed:
                    continue
            else:
                regime = None

            # Today's session for setup context
            today_session = df[cet_dates == today].loc[:ts]
            history = df.loc[:ts]
            best: Optional[Signal] = None
            for setup in setups:
                try:
                    if isinstance(setup, OrbDaxSetupV331):
                        sig = setup.check_entry_at(today_session, daily_history,
                                                    ts, regime, history_5m=history)
                    elif isinstance(setup, UsMomentumSetupV331):
                        sig = setup.check_entry_at(history, daily_history, ts,
                                                    regime, sp500_5m=None)
                    elif isinstance(setup, OrbDaxSetup):
                        sig = setup.check_entry_at(today_session, daily_history,
                                                    ts, history_5m=history)
                    elif isinstance(setup, VwapBounceSetup):
                        sig = setup.check_entry_at(today_session, ts,
                                                    history_5m=history)
                    elif isinstance(setup, UsMomentumSetup):
                        sig = setup.check_entry_at(history, daily_history, ts,
                                                    sp500_5m=None)
                    else:
                        sig = None
                except Exception as e:
                    result.invariant_violations.append(
                        f"setup {setup.name} crashed @ {ts}: {e}"
                    )
                    sig = None
                if sig is not None and (best is None or sig.confidence > best.confidence):
                    best = sig

            if best is None:
                continue

            # Position sizing + RRR check
            sl_points = abs(best.entry - best.sl)
            setup_type_for_sizing = "A" if best.filters_met == best.filters_total else "B"
            if use_v331 and regime is not None:
                sized = calculate_lots_v331(
                    setup_type_for_sizing, risk_state, regime,
                    sl_points, eur_usd_spot,
                    equity_usd=equity_usd, dax_price=float(row["close"]))
            else:
                sized = compute_lots(setup_type_for_sizing, risk_state,
                                      sl_points, eur_usd_spot,
                                      equity_usd=equity_usd,
                                      dax_price=float(row["close"]))
            if sized.lots == 0:
                continue
            if not rrr_acceptable(best.entry, best.sl, best.tp).allowed:
                continue

            open_pos = OpenPosition(
                setup=best.setup_name, direction=best.direction,
                entry_ts=ts, entry=best.entry,
                sl=best.sl, tp=best.tp,
                lots=sized.lots, risk_usd=sized.risk_usd,
                filters_met=best.filters_met,
                filters_total=best.filters_total,
            )

    # Close any still-open at end of feed
    if open_pos is not None:
        last_ts = df.index[-1]
        last_close = float(df.iloc[-1]["close"])
        pnl = _pnl_usd(open_pos.direction, open_pos.entry, last_close,
                        open_pos.lots, eur_usd_spot)
        result.trades.append(Trade(
            setup=open_pos.setup, direction=open_pos.direction,
            entry_ts=open_pos.entry_ts, exit_ts=last_ts,
            entry=open_pos.entry, exit=last_close,
            sl=open_pos.sl, tp=open_pos.tp,
            lots=open_pos.lots, risk_usd=open_pos.risk_usd,
            pnl_usd=pnl, exit_reason="end_of_feed",
            filters_met=open_pos.filters_met,
            filters_total=open_pos.filters_total,
        ))
    return result
