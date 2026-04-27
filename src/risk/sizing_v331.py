"""Regime-aware position sizing wrapper pro Strategy v3.3.1.

Builds on top of risk_manager.compute_lots() (FX-C + Black Swan Cap + margin cap)
adding regime risk multipliers per v3.3.1 §2.3:

  TREND      1.0×  (full risk)
  CALM       0.7×  (reduced — range/rotation regime)
  CRASH      0.5×  (heavily reduced — panic protection)
  UNDEFINED  0.0×  (NO TRADE)

The multiplier scales the *risk_usd* parameter forwarded to compute_lots(),
which proportionally reduces lots while keeping BSC and margin caps intact
(safety-first: caps protect, multiplier is additional reduction).

Spec: Strategy v3.3.1 §2.3.
"""
from __future__ import annotations

from typing import Optional

from src.risk.risk_manager import (
    SizingResult, RiskState, RISK_TABLE, compute_lots,
)
from src.strategy.regime import Regime

REGIME_RISK_MULTIPLIERS: dict[Regime, float] = {
    Regime.TREND: 1.0,
    Regime.CALM: 0.7,
    Regime.CRASH: 0.5,
    Regime.UNDEFINED: 0.0,
}


def calculate_lots_v331(
    setup_type: str,
    risk_state: RiskState,
    regime: Regime,
    sl_points: float,
    eur_usd_spot: float,
    *,
    equity_usd: float = 100_000.0,
    dax_price: Optional[float] = None,
    leverage: int = 30,
    lot_step: float = 0.01,
    min_lots: float = 0.01,
) -> SizingResult:
    """Compute regime-adjusted lots.

    Mechanics:
      1. Lookup base risk_usd from RISK_TABLE[setup_type, risk_state].
      2. Multiply by REGIME_RISK_MULTIPLIERS[regime].
      3. UNDEFINED → return 0 lots immediately (NO TRADE).
      4. Forward adjusted risk_usd into compute_lots() → respects BSC + margin caps.

    Returns:
        SizingResult with detail.regime_multiplier added.
    """
    if regime == Regime.UNDEFINED:
        return SizingResult(
            lots=0.0, risk_usd=0.0, capped_by="regime_undefined",
            detail={"regime": regime.value, "reason": "UNDEFINED → NO TRADE"},
        )
    multiplier = REGIME_RISK_MULTIPLIERS.get(regime)
    if multiplier is None:
        raise ValueError(f"unknown regime {regime}")

    base_risk = RISK_TABLE.get((setup_type, risk_state))
    if base_risk is None:
        raise ValueError(f"unknown (setup_type, risk_state): {setup_type, risk_state}")
    if base_risk <= 0:
        return SizingResult(
            lots=0.0, risk_usd=0.0, capped_by="disabled",
            detail={"regime": regime.value,
                     "reason": f"{setup_type}/{risk_state} risk_usd=0"},
        )

    adjusted_risk = base_risk * multiplier
    if adjusted_risk <= 0:
        return SizingResult(
            lots=0.0, risk_usd=0.0, capped_by="regime_multiplier_zero",
            detail={"regime": regime.value, "multiplier": multiplier},
        )

    # Patch RISK_TABLE temporarily? No — compute_lots reads RISK_TABLE.
    # Instead: solve forward by computing target lots ourselves with adjusted risk_usd.
    # Easier: call compute_lots and then scale. But compute_lots applies BSC/margin
    # which are absolute (not risk-scaled). Cleanest: monkey-substitute is brittle.
    # Approach: compute base sizing, then scale standard branch by multiplier; caps
    # remain unchanged. Rebuild SizingResult.
    base = compute_lots(setup_type, risk_state, sl_points, eur_usd_spot,
                         equity_usd=equity_usd, dax_price=dax_price,
                         leverage=leverage, lot_step=lot_step, min_lots=min_lots)
    if base.lots == 0:
        # already disabled or zero; return as-is with regime annotation
        d = dict(base.detail)
        d["regime"] = regime.value
        d["regime_multiplier"] = multiplier
        return SizingResult(lots=0.0, risk_usd=0.0,
                             capped_by=base.capped_by, detail=d)

    # Apply multiplier to standard branch only; BSC/margin caps unchanged.
    candidates = dict(base.detail.get("candidates", {}))
    candidates["standard"] = candidates.get("standard", 0.0) * multiplier
    capped_by = min(candidates, key=candidates.get)
    lots_raw = candidates[capped_by]
    import math
    lots_floored = math.floor(lots_raw / lot_step) * lot_step
    if lots_floored < min_lots:
        return SizingResult(
            lots=0.0, risk_usd=0.0, capped_by="below_min_after_multiplier",
            detail={"regime": regime.value, "multiplier": multiplier,
                     "candidates": candidates, "raw": lots_raw},
        )
    return SizingResult(
        lots=round(lots_floored, 2),
        risk_usd=adjusted_risk,
        capped_by=capped_by,
        detail={
            "regime": regime.value,
            "regime_multiplier": multiplier,
            "candidates": candidates,
            "raw": lots_raw,
            "lot_step": lot_step,
            "leverage": leverage,
            "equity_usd": equity_usd,
            "dax_price": dax_price,
        },
    )
