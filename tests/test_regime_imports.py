"""Sekce 1 import-level tests pro src.strategy.regime skeleton.

Plná regime logic dorazí v Sekci 2 — tyto testy ověřují jen že:
  1. import funguje
  2. Regime enum má přesně 4 hodnoty (TREND/CALM/CRASH/UNDEFINED)
  3. RegimeSignals se dá instanciovat (dataclass kontrakt)
  4. stub funkce vyhazují NotImplementedError (chrání před tichým "default" fallthrough)
  5. persistence.get_active_regime je callable a má správný stub status
"""
from __future__ import annotations

import datetime as dt

import pytest


def test_imports_succeed():
    """Module-level import bez exception."""
    import src.strategy.regime as regime  # noqa: F401
    from src.strategy.regime import (
        Regime, RegimeSignals, classify_regime_raw, get_active_regime,  # noqa: F401
    )


def test_regime_enum_has_four_values():
    from src.strategy.regime import Regime
    values = {r.value for r in Regime}
    assert values == {"TREND", "CALM", "CRASH", "UNDEFINED"}
    assert len(list(Regime)) == 4


def test_regime_signals_dataclass_instantiates():
    from src.strategy.regime import RegimeSignals
    s = RegimeSignals(
        ts=dt.datetime(2026, 4, 27, 8, 0, tzinfo=dt.timezone.utc),
        atr_pct_label="NORMAL", atr_pct_value=1.0,
        adx_h4_label="MODERATE", adx_h4_value=22.5,
        ema_slope_label="UP", ema_slope_value=0.001,
    )
    assert s.atr_pct_label == "NORMAL"
    assert s.adx_h4_value == 22.5
    assert s.ema_slope_label == "UP"


def test_classify_regime_raw_returns_regime_enum():
    """Post-Sekce-2 smoke: full impl returns Regime, not raises."""
    from src.strategy.regime import classify_regime_raw, RegimeSignals, Regime
    s = RegimeSignals(
        ts=dt.datetime(2026, 4, 27, 8, 0, tzinfo=dt.timezone.utc),
        atr_pct_label="HIGH", atr_pct_value=1.8,
        adx_h4_label="WEAK", adx_h4_value=15.0,
        ema_slope_label="DOWN", ema_slope_value=-0.0006,
    )
    result = classify_regime_raw(s)
    assert isinstance(result, Regime)
    assert result == Regime.CRASH  # HIGH+DOWN → CRASH per spec


def test_get_active_regime_returns_regime_enum():
    """Post-Sekce-2 smoke: full impl returns Regime, not raises."""
    from src.strategy.regime import Regime, get_active_regime
    result = get_active_regime(history=[Regime.CALM, Regime.CALM],
                                raw_today=Regime.TREND,
                                current_active=Regime.CALM)
    # 1-day TREND signal vs 2-day consensus rule → stay CALM
    assert isinstance(result, Regime)
    assert result == Regime.CALM
