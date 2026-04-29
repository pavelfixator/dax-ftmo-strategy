"""Tests pro v3.3.4 realistic per-trade sizing in gate18_block_bootstrap."""
from __future__ import annotations

import pytest

from scripts.gate18_block_bootstrap import (
    realistic_lots, _pnl_pts_to_usd,
    BSC_CAP_LOTS, GATE18_REGIME_MULTIPLIERS,
    EUR_USD, RISK_USD_PER_TRADE,
)
from src.strategy.regime import Regime


class TestRealisticLots:
    def test_pavel_example_sl60_trend(self):
        # v3.3.5 STEP 2: SL=60, TREND mult 1.0: 1250/(60×1.08)×1.0 = 19.29
        # (STEP 1 historical was 15.43; see phase0_step1_report.md)
        assert realistic_lots("us_momentum", Regime.TREND, sl_pts=60) == pytest.approx(19.29, abs=0.01)

    def test_pavel_example_sl50_crash_v3_3_5_step_2(self):
        # v3.3.5 STEP 2: CRASH mult 1.0 (kept) × $1250 base risk
        # SL=50, CRASH mult 1.0: 1250/(50×1.08)×1.0 = 23.148 → BSC BINDING
        # (STEP 1 historical was 18.52; see phase0_step1_report.md)
        assert realistic_lots("us_momentum", Regime.CRASH, sl_pts=50) == pytest.approx(BSC_CAP_LOTS, abs=0.01)

    def test_pavel_example_sl80_calm(self):
        # v3.3.5 STEP 2: SL=80, CALM mult 1.0: 1250/(80×1.08)×1.0 = 14.47
        assert realistic_lots("us_momentum", Regime.CALM, sl_pts=80) == pytest.approx(14.47, abs=0.01)

    def test_orb_dax_calm_uses_avg_sl(self):
        # v3.3.5 STEP 2: AVG_SL[orb_dax,CALM]=50, mult 1.0
        # 1250/(50×1.08)×1.0 = 23.148 → BSC BINDING (saturation per POZNÁMKA #1)
        assert realistic_lots("orb_dax", Regime.CALM) == pytest.approx(BSC_CAP_LOTS, abs=0.01)

    def test_undefined_returns_zero(self):
        assert realistic_lots("orb_dax", Regime.CALM, sl_pts=50) > 0
        # UNDEFINED mult is 0 → 0 lots
        assert realistic_lots("anything", Regime.UNDEFINED, sl_pts=50) == 0.0

    def test_bsc_cap_applied_for_tight_sl(self):
        # v3.3.5 STEP 2: SL=10 → 1250/(10×1.08)×1.0 = 115.74, capped to BSC ≈ 23.15
        assert realistic_lots("us_momentum", Regime.TREND, sl_pts=10) == pytest.approx(BSC_CAP_LOTS, abs=0.01)

    def test_zero_or_negative_sl_returns_zero(self):
        assert realistic_lots("us_momentum", Regime.TREND, sl_pts=0) == 0.0
        assert realistic_lots("us_momentum", Regime.TREND, sl_pts=-5) == 0.0

    def test_crash_matches_trend_v3_3_5_step_2(self):
        # v3.3.5 STEP 2: CRASH mult 1.0 (kept from STEP 1) → matches TREND magnitude
        # SL=70 → 1250/(70×1.08)×1.0 = 16.53 (below BSC, both standard-bound)
        trend_lots = realistic_lots("us_momentum", Regime.TREND, sl_pts=70)
        crash_lots = realistic_lots("us_momentum", Regime.CRASH, sl_pts=70)
        assert crash_lots == pytest.approx(trend_lots, rel=0.01)
        assert 16.0 <= crash_lots <= 17.0  # STEP 2 production value


class TestPnlConversion:
    def test_basic(self):
        # 100 pts × 10 lots × 1.08 = 1080 USD
        assert _pnl_pts_to_usd(100, 10) == pytest.approx(1080.0)

    def test_negative(self):
        assert _pnl_pts_to_usd(-50, 5) == pytest.approx(-50 * 5 * EUR_USD)

    def test_zero_lots(self):
        assert _pnl_pts_to_usd(50, 0) == 0.0


class TestConstants:
    def test_risk_per_trade_v3_3_5_step_2(self):
        # v3.3.5 STEP 2: 1% → 1.25% of $100K account
        # (mirror of risk_manager.RISK_TABLE[("A", "normal")] = 1250)
        assert RISK_USD_PER_TRADE == 1_250.0

    def test_eur_usd(self):
        assert EUR_USD == 1.08

    def test_multipliers_v3_3_5_step_2(self):
        # v3.3.5 STEP 2: same multipliers as STEP 1 (only base risk uplift)
        assert GATE18_REGIME_MULTIPLIERS[Regime.TREND] == 1.0
        assert GATE18_REGIME_MULTIPLIERS[Regime.CALM] == 1.0
        assert GATE18_REGIME_MULTIPLIERS[Regime.CRASH] == 1.0
        assert GATE18_REGIME_MULTIPLIERS[Regime.UNDEFINED] == 0.0

    def test_bsc_cap_value(self):
        # 5000 / (200 × 1.08) ≈ 23.148
        assert BSC_CAP_LOTS == pytest.approx(23.148, abs=0.01)
