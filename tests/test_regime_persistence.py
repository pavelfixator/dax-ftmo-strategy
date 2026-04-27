"""Tests pro src.strategy.regime.persistence — asymmetric switch rule."""
from __future__ import annotations

import pytest

from src.strategy.regime import Regime, get_active_regime


# ============================================================
# Cold start (current_active is None)
# ============================================================

class TestColdStart:
    def test_cold_start_returns_raw_today(self):
        assert get_active_regime([], Regime.TREND) == Regime.TREND

    def test_cold_start_returns_crash_directly(self):
        assert get_active_regime([], Regime.CRASH) == Regime.CRASH

    def test_cold_start_returns_undefined(self):
        assert get_active_regime([], Regime.UNDEFINED) == Regime.UNDEFINED


# ============================================================
# Rule 1: instant switch TO CRASH (panic protection)
# ============================================================

class TestInstantSwitchToCrash:
    def test_calm_to_crash_instant(self):
        assert get_active_regime([Regime.CALM], Regime.CRASH,
                                  current_active=Regime.CALM) == Regime.CRASH

    def test_trend_to_crash_instant(self):
        assert get_active_regime([Regime.TREND, Regime.TREND],
                                  Regime.CRASH,
                                  current_active=Regime.TREND) == Regime.CRASH

    def test_undefined_to_crash_instant(self):
        assert get_active_regime([Regime.UNDEFINED], Regime.CRASH,
                                  current_active=Regime.UNDEFINED) == Regime.CRASH


# ============================================================
# Rule 2: exit FROM CRASH requires 2 consecutive non-CRASH days
# ============================================================

class TestExitFromCrash:
    def test_one_non_crash_day_keeps_crash(self):
        # Yesterday was still CRASH, today raw is CALM → only 1 non-CRASH day
        result = get_active_regime([Regime.CRASH], Regime.CALM,
                                    current_active=Regime.CRASH)
        assert result == Regime.CRASH

    def test_two_consecutive_non_crash_exits_to_today(self):
        # Yesterday raw = CALM, today raw = CALM → 2 non-CRASH days → exit to CALM
        result = get_active_regime([Regime.CALM], Regime.CALM,
                                    current_active=Regime.CRASH)
        assert result == Regime.CALM

    def test_two_consecutive_non_crash_different_regimes(self):
        # Yesterday TREND, today CALM — both non-CRASH → exit to today's raw
        result = get_active_regime([Regime.TREND], Regime.CALM,
                                    current_active=Regime.CRASH)
        assert result == Regime.CALM

    def test_yesterday_undefined_today_trend_exits(self):
        result = get_active_regime([Regime.UNDEFINED], Regime.TREND,
                                    current_active=Regime.CRASH)
        assert result == Regime.TREND


# ============================================================
# Rule 3: non-CRASH ↔ non-CRASH switches require 2-day consensus
# ============================================================

class TestNonCrashSwitches:
    def test_one_day_signal_keeps_current(self):
        # current=TREND, yesterday=TREND, today=CALM → only 1-day CALM signal
        result = get_active_regime([Regime.TREND], Regime.CALM,
                                    current_active=Regime.TREND)
        assert result == Regime.TREND

    def test_two_day_consensus_switches(self):
        # current=TREND, yesterday=CALM, today=CALM → 2-day CALM consensus
        result = get_active_regime([Regime.CALM], Regime.CALM,
                                    current_active=Regime.TREND)
        assert result == Regime.CALM

    def test_same_regime_keeps_current(self):
        # current=CALM, today=CALM (no change attempted)
        result = get_active_regime([Regime.TREND], Regime.CALM,
                                    current_active=Regime.CALM)
        assert result == Regime.CALM

    def test_three_day_history_takes_latest_two(self):
        # current=TREND. History = [CALM, UNDEFINED]. Today = UNDEFINED.
        # Yesterday raw (history[-1]) = UNDEFINED, today = UNDEFINED → 2-day consensus.
        result = get_active_regime([Regime.CALM, Regime.UNDEFINED],
                                    Regime.UNDEFINED,
                                    current_active=Regime.TREND)
        assert result == Regime.UNDEFINED

    def test_no_consensus_after_flip_flop(self):
        # current=TREND, yesterday=UNDEFINED, today=CALM → no consensus, stay TREND
        result = get_active_regime([Regime.UNDEFINED], Regime.CALM,
                                    current_active=Regime.TREND)
        assert result == Regime.TREND

    def test_undefined_to_trend_with_consensus(self):
        # current=UNDEFINED, yesterday=TREND, today=TREND
        result = get_active_regime([Regime.TREND], Regime.TREND,
                                    current_active=Regime.UNDEFINED)
        assert result == Regime.TREND


# ============================================================
# Edge cases
# ============================================================

class TestEdgeCases:
    def test_empty_history_with_current_active_keeps_current(self):
        # current=TREND, history=[] (no yesterday data), today=CALM
        # → no consensus possible → stay TREND
        result = get_active_regime([], Regime.CALM, current_active=Regime.TREND)
        assert result == Regime.TREND

    def test_empty_history_today_same_as_current(self):
        result = get_active_regime([], Regime.TREND, current_active=Regime.TREND)
        assert result == Regime.TREND

    def test_crash_today_with_no_history(self):
        # Rule 1 fires regardless of history
        result = get_active_regime([], Regime.CRASH, current_active=Regime.TREND)
        assert result == Regime.CRASH

    def test_long_history_only_uses_last_entry(self):
        # 5 days of history; only history[-1] matters per spec
        history = [Regime.TREND, Regime.TREND, Regime.TREND, Regime.CALM, Regime.CALM]
        result = get_active_regime(history, Regime.CALM,
                                    current_active=Regime.TREND)
        # yesterday=CALM, today=CALM → 2-day consensus → switch to CALM
        assert result == Regime.CALM
