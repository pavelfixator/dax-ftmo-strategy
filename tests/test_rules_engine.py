"""Tests pro src.risk.rules_engine."""
from __future__ import annotations

import datetime as dt

import pytest

from src.risk.rules_engine import (
    in_trading_window, before_hard_stop, is_holiday,
    near_news, gap_too_large, max_positions, rrr_acceptable,
    request_budget_ok, get_nyse_open_cet, CET,
)


def cet(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=CET)


class TestTradingWindow:
    def test_mon_morning_in_window(self):
        assert in_trading_window(cet(2026, 4, 27, 9)).allowed  # Mon

    def test_mon_before_open(self):
        assert not in_trading_window(cet(2026, 4, 27, 7, 30)).allowed

    def test_mon_after_close(self):
        assert not in_trading_window(cet(2026, 4, 27, 18, 1)).allowed

    def test_fri_until_16(self):
        assert in_trading_window(cet(2026, 5, 1, 15, 30)).allowed
        assert not in_trading_window(cet(2026, 5, 1, 16, 1)).allowed

    def test_saturday_blocked(self):
        assert not in_trading_window(cet(2026, 5, 2, 12)).allowed


class TestHardStop:
    def test_mon_before_2000(self):
        assert before_hard_stop(cet(2026, 4, 27, 19, 30)).allowed

    def test_mon_after_2000(self):
        assert not before_hard_stop(cet(2026, 4, 27, 20, 1)).allowed

    def test_fri_cutoff_1955(self):
        assert before_hard_stop(cet(2026, 5, 1, 19, 50)).allowed
        assert not before_hard_stop(cet(2026, 5, 1, 19, 56)).allowed


def test_holiday_check():
    holidays = {dt.date(2026, 5, 1)}  # German Labour Day
    assert not is_holiday(cet(2026, 5, 1, 12), holidays).allowed
    assert is_holiday(cet(2026, 4, 30, 12), holidays).allowed


class TestNews:
    def test_within_60min_default(self):
        events = [{"ts_utc": "2026-05-04T18:30:00+00:00", "title": "Some Event"}]
        # 30 min before — blocked
        assert not near_news(cet(2026, 5, 4, 19, 0), events).allowed

    def test_outside_window(self):
        events = [{"ts_utc": "2026-05-04T12:00:00+00:00", "title": "Some Event"}]
        assert near_news(cet(2026, 5, 4, 16, 0), events).allowed

    def test_ecb_rate_wider_window(self):
        events = [{"ts_utc": "2026-05-04T12:15:00+00:00",
                   "title": "ECB Rate Decision"}]
        # 75 min after = within 90min ECB window → blocked
        ts = dt.datetime(2026, 5, 4, 13, 30, tzinfo=dt.timezone.utc)
        assert not near_news(ts, events).allowed
        # 95 min after — outside 90min window
        ts2 = dt.datetime(2026, 5, 4, 13, 50, tzinfo=dt.timezone.utc)
        assert near_news(ts2, events).allowed


class TestGap:
    def test_small_gap_ok(self):
        assert gap_too_large(24000, 24100).allowed  # 0.42 % gap

    def test_large_gap_blocked(self):
        assert not gap_too_large(24000, 24300).allowed  # 1.25 %

    def test_negative_gap(self):
        assert not gap_too_large(24000, 23700).allowed  # -1.25 %

    def test_zero_close_raises(self):
        with pytest.raises(ValueError):
            gap_too_large(0, 100)


def test_max_positions():
    assert max_positions(0).allowed
    assert not max_positions(1).allowed


class TestRRR:
    def test_long_rrr_2_ok(self):
        assert rrr_acceptable(100, 90, 120).allowed  # risk=10, reward=20 → 2.0

    def test_long_rrr_below_2(self):
        assert not rrr_acceptable(100, 95, 108).allowed  # 1.6

    def test_short_rrr_3(self):
        assert rrr_acceptable(100, 110, 70).allowed  # risk=10, reward=30


def test_request_budget():
    assert request_budget_ok(500).allowed
    assert not request_budget_ok(900).allowed  # >= 882
    assert request_budget_ok(881).allowed


class TestNyseOpen:
    def test_winter_default(self):
        assert get_nyse_open_cet(dt.date(2026, 1, 15)) == dt.time(15, 30)

    def test_us_spring_gap(self):
        assert get_nyse_open_cet(dt.date(2026, 3, 15)) == dt.time(14, 30)

    def test_summer_default(self):
        assert get_nyse_open_cet(dt.date(2026, 6, 15)) == dt.time(15, 30)

    def test_us_autumn_gap(self):
        assert get_nyse_open_cet(dt.date(2026, 10, 27)) == dt.time(14, 30)

    def test_late_october_eu_summer_still(self):
        # Oct 20 — both EU and US in DST (EU until Oct 25)
        assert get_nyse_open_cet(dt.date(2026, 10, 20)) == dt.time(15, 30)
