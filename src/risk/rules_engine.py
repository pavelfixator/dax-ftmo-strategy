"""FTMO + custom rules engine.

Funkce vracejí (allowed: bool, reason: str) pro snadný audit log.
Žádný state — caller předává market data, account state, news DB.

Pravidla:
  trading_window — Po-Čt 08:00-18:00 CET, Pá 08:00-16:00 CET
  hard_stop_entries — 1 h před forced close (Po-Čt 20:00, Pá 19:55)
  forced_close — Po-Čt 20:55 CET, Pá 20:45 CET
  no_overnight — naše pravidlo (FTMO Swing povoluje, my ne)
  news — high impact ±60min default; ECB rate ±90min, FOMC ±90min
  holiday — DE+US holiday calendar (caller provides set of dates)
  max_positions — 1 (FTMO no-hedging)
  rrr_min — 2.0
  hyperactivity — request budget 882/day per Strategy v3.2

Spec: Strategy v3.2 §"Tvrdá pravidla" + 00-System/Trading-Hours.md +
00-System/FTMO-Rules.md.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Optional

CET = dt.timezone(dt.timedelta(hours=1))  # winter; DST handled by zoneinfo if needed
TRADING_START_CET = dt.time(8, 0)
TRADING_END_CET_MON_THU = dt.time(18, 0)
TRADING_END_CET_FRI = dt.time(16, 0)
HARD_STOP_ENTRIES_MON_THU = dt.time(20, 0)  # 1h before 20:55 forced close
HARD_STOP_ENTRIES_FRI = dt.time(19, 55)
FORCED_CLOSE_MON_THU = dt.time(20, 55)
FORCED_CLOSE_FRI = dt.time(20, 45)

NEWS_WINDOW_DEFAULT = dt.timedelta(minutes=60)
NEWS_WINDOW_ECB_RATE = dt.timedelta(minutes=90)
NEWS_WINDOW_LAGARDE = dt.timedelta(minutes=45)
NEWS_WINDOW_POWELL = dt.timedelta(minutes=30)


@dataclass(frozen=True)
class RuleResult:
    allowed: bool
    reason: str


def _to_cet(ts: dt.datetime) -> dt.datetime:
    """Convert tz-aware datetime to fixed CET (UTC+1).

    For DST-correct conversion use zoneinfo at call site; this engine treats
    CET as fixed offset for window comparisons (entry windows are local
    business hours, not wall-clock). Caller may override.
    """
    if ts.tzinfo is None:
        raise ValueError("ts must be tz-aware")
    return ts.astimezone(CET)


def in_trading_window(ts: dt.datetime) -> RuleResult:
    """Po-Čt 08:00-18:00, Pá 08:00-16:00, So-Ne zakázáno."""
    cet = _to_cet(ts)
    wd = cet.weekday()  # 0=Mon, 4=Fri, 5=Sat
    t = cet.time()
    if wd >= 5:
        return RuleResult(False, "weekend")
    if wd == 4:
        if not (TRADING_START_CET <= t < TRADING_END_CET_FRI):
            return RuleResult(False, f"Friday outside 08:00-16:00 CET (now {t})")
    else:
        if not (TRADING_START_CET <= t < TRADING_END_CET_MON_THU):
            return RuleResult(False, f"Mon-Thu outside 08:00-18:00 CET (now {t})")
    return RuleResult(True, "in trading window")


def before_hard_stop(ts: dt.datetime) -> RuleResult:
    """No new entries 1h before forced close."""
    cet = _to_cet(ts)
    wd = cet.weekday()
    t = cet.time()
    cutoff = HARD_STOP_ENTRIES_FRI if wd == 4 else HARD_STOP_ENTRIES_MON_THU
    if t >= cutoff:
        return RuleResult(False, f"past hard-stop entries cutoff ({cutoff})")
    return RuleResult(True, "before hard-stop")


def is_holiday(ts: dt.datetime, holiday_set: Iterable[dt.date]) -> RuleResult:
    cet = _to_cet(ts)
    if cet.date() in set(holiday_set):
        return RuleResult(False, f"holiday {cet.date().isoformat()}")
    return RuleResult(True, "not a holiday")


def near_news(
    ts: dt.datetime,
    news_events: Iterable[dict],
    *,
    default_window: dt.timedelta = NEWS_WINDOW_DEFAULT,
) -> RuleResult:
    """News events: list of dicts with 'ts_utc' (ISO str) and 'title' (str).

    Different windows for ECB rate / Lagarde press / FOMC / Powell — best-effort
    inferred from title substrings. Default ±60min.
    """
    if ts.tzinfo is None:
        raise ValueError("ts must be tz-aware")
    ts_utc = ts.astimezone(dt.timezone.utc)
    for ev in news_events:
        ev_ts = dt.datetime.fromisoformat(ev["ts_utc"])
        if ev_ts.tzinfo is None:
            ev_ts = ev_ts.replace(tzinfo=dt.timezone.utc)
        title_lower = (ev.get("title") or "").lower()
        if "rate decision" in title_lower:
            window = NEWS_WINDOW_ECB_RATE
        elif "press conference" in title_lower:
            window = NEWS_WINDOW_LAGARDE
        elif "fomc" in title_lower:
            window = NEWS_WINDOW_DEFAULT  # Powell-specific narrower window applied separately
        else:
            window = default_window
        if abs((ts_utc - ev_ts).total_seconds()) <= window.total_seconds():
            return RuleResult(False, f"near news '{ev.get('title')}' @ {ev_ts.isoformat()}")
    return RuleResult(True, "no news in window")


def gap_too_large(prev_close: float, today_open: float,
                  threshold_pct: float = 0.01) -> RuleResult:
    """Gap > 1 % → no-trade rationale (gap reversal risk)."""
    if prev_close <= 0:
        raise ValueError("prev_close must be > 0")
    gap = (today_open - prev_close) / prev_close
    if abs(gap) > threshold_pct:
        return RuleResult(False, f"gap {gap:.2%} > threshold {threshold_pct:.2%}")
    return RuleResult(True, f"gap {gap:.2%} within threshold")


def max_positions(open_count: int, limit: int = 1) -> RuleResult:
    if open_count >= limit:
        return RuleResult(False, f"{open_count} open positions ≥ limit {limit} (FTMO no-hedging)")
    return RuleResult(True, f"{open_count}/{limit} positions open")


def rrr_acceptable(entry: float, sl: float, tp: float, min_rrr: float = 2.0) -> RuleResult:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk == 0:
        return RuleResult(False, "zero risk (entry==sl)")
    rrr = reward / risk
    if rrr < min_rrr:
        return RuleResult(False, f"RRR {rrr:.2f} < min {min_rrr}")
    return RuleResult(True, f"RRR {rrr:.2f}")


def request_budget_ok(used_today: int, limit: int = 882) -> RuleResult:
    """Strategy v3.2: 882/day = 44% of FTMO 2000/day limit."""
    if used_today >= limit:
        return RuleResult(False, f"daily request budget exhausted {used_today}/{limit}")
    return RuleResult(True, f"requests {used_today}/{limit}")


def get_nyse_open_cet(d: dt.date) -> dt.time:
    """NYSE 9:30 ET converted to local CET/CEST.

    Spec: Trading-Hours.md table. Returns wall-clock time on given date.
    Two gap windows where offset is non-standard:
      - 2026-03-08 .. 2026-03-28 (US spring gap, EU still CET) → 14:30 CET
      - 2026-10-25 .. 2026-10-31 (US autumn gap, EU back to CET) → 14:30 CET
    """
    if dt.date(2026, 3, 8) <= d <= dt.date(2026, 3, 28):
        return dt.time(14, 30)
    if dt.date(2026, 10, 25) <= d <= dt.date(2026, 10, 31):
        return dt.time(14, 30)
    # Default: 15:30 in both winter (CET+EST) and summer (CEST+EDT)
    return dt.time(15, 30)
