"""Tests pro src.risk.risk_manager — sizing + risk state derivation."""
from __future__ import annotations

import math

import pytest

from src.risk.risk_manager import (
    compute_lots,
    derive_risk_state,
    BLACK_SWAN_POINTS,
    BLACK_SWAN_USD_CAP,
)


# Reference: Strategy v3.2 spec EURUSD=1.08, DAX=24155 → cap ~23.15 lots
EURUSD = 1.08
DAX_PRICE = 24155.0


class TestComputeLots:
    def test_a_normal_uncapped_below_bsc(self):
        # Wide SL → standard lots small → BSC won't bind
        # v3.3.5 STEP 2: 1250 / (200 * 1.08) = 5.79 → floor 0.01 = 5.78
        r = compute_lots("A", "normal", sl_points=200, eur_usd_spot=EURUSD)
        assert r.lots == pytest.approx(5.78, abs=0.01)
        assert r.capped_by == "standard"
        assert r.risk_usd == 1250

    def test_b_normal_half_of_a(self):
        ra = compute_lots("A", "normal", sl_points=100, eur_usd_spot=EURUSD)
        rb = compute_lots("B", "normal", sl_points=100, eur_usd_spot=EURUSD)
        # If both are capped by standard: ratio = 500/1000 = 0.5
        if ra.capped_by == "standard" and rb.capped_by == "standard":
            assert rb.lots / ra.lots == pytest.approx(0.5, rel=0.02)

    def test_b_warning_disabled(self):
        r = compute_lots("B", "warning", sl_points=100, eur_usd_spot=EURUSD)
        assert r.lots == 0
        assert r.capped_by == "disabled"

    def test_disabled_state_zeroes_both(self):
        ra = compute_lots("A", "disabled", sl_points=50, eur_usd_spot=EURUSD)
        rb = compute_lots("B", "disabled", sl_points=50, eur_usd_spot=EURUSD)
        assert ra.lots == 0 and rb.lots == 0
        assert ra.capped_by == "disabled" and rb.capped_by == "disabled"

    def test_black_swan_cap_binds_for_tight_sl(self):
        # SL 30 points → standard lots huge → BSC must cap
        r = compute_lots("A", "normal", sl_points=30, eur_usd_spot=EURUSD)
        bsc_expected = BLACK_SWAN_USD_CAP / (BLACK_SWAN_POINTS * EURUSD)
        # ~23.15
        assert r.capped_by == "black_swan_cap"
        assert r.lots == pytest.approx(math.floor(bsc_expected * 100) / 100, abs=0.01)

    def test_margin_cap_caught_at_low_equity(self):
        # 10k equity → 30% = 3000 margin → at DAX 24155 EUR/lot, 1:30 →
        # margin per lot = 24155 * 1.08 / 30 = 869 USD → cap = 3000/869 = 3.45 lots
        r = compute_lots("A", "normal", sl_points=30, eur_usd_spot=EURUSD,
                         equity_usd=10_000, dax_price=DAX_PRICE)
        assert r.capped_by == "margin_cap"
        expected = 0.30 * 10_000 / (DAX_PRICE * EURUSD / 30)
        assert r.lots == pytest.approx(math.floor(expected * 100) / 100, abs=0.01)

    def test_invalid_sl_raises(self):
        with pytest.raises(ValueError):
            compute_lots("A", "normal", sl_points=0, eur_usd_spot=EURUSD)

    def test_invalid_eurusd_raises(self):
        with pytest.raises(ValueError):
            compute_lots("A", "normal", sl_points=50, eur_usd_spot=0)


class TestDeriveRiskState:
    def test_normal_baseline(self):
        assert derive_risk_state(0) == "normal"

    def test_caution_on_small_gap(self):
        assert derive_risk_state(0, gap_pct=0.007) == "caution"
        # Gap below caution range → still normal
        assert derive_risk_state(0, gap_pct=0.003) == "normal"

    def test_warning_on_l1(self):
        assert derive_risk_state(-5500) == "warning"

    def test_disabled_on_hard_stop(self):
        assert derive_risk_state(-7500) == "disabled"

    def test_disabled_on_consecutive_losses(self):
        assert derive_risk_state(0, consecutive_losses=5) == "disabled"

    def test_disabled_on_weekly_pause(self):
        assert derive_risk_state(0, weekly_pnl_usd=-4500) == "disabled"

    def test_priority_disabled_over_warning(self):
        # Cumulative -8000 (would be warning by L1 alone) → disabled
        assert derive_risk_state(-8000) == "disabled"
