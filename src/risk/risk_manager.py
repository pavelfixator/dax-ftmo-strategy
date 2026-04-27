"""Position sizing + risk-state lookup per Strategy v3.2.

Position sizing model:
    lots_standard = risk_usd / (sl_eff_points × eur_usd_spot)
    lots_bsc      = 5000 / (200 × eur_usd_spot)            # Black Swan Cap
    lots_margin   = 0.30 × equity_usd / (face_value_per_lot_usd / leverage)
    lots_final    = min(standard, bsc, margin) → floored to lot_step

Risk state je discrete:
    normal  — žádný DD trigger
    caution — gap day 0.5-1 % (otevírací mezera)
    warning — cumulative DD ≤ −5000 USD (L1 trigger)
    disabled — L2 (cumulative ≤ −7000), no new positions

Risk table (A/B × state):
    | state    | A    | B   |
    |----------|------|-----|
    | normal   | 1000 | 500 |
    | caution  |  600 | 300 |
    | warning  |  700 |   0 |
    | disabled |    0 |   0 |

Spec: Strategy v3.2 § "Position sizing (FX verze C + Black Swan Cap)".
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional

SetupType = Literal["A", "B"]
RiskState = Literal["normal", "caution", "warning", "disabled"]

RISK_TABLE: dict[tuple[SetupType, RiskState], float] = {
    ("A", "normal"):   1000.0,
    ("A", "caution"):   600.0,
    ("A", "warning"):   700.0,
    ("A", "disabled"):    0.0,
    ("B", "normal"):    500.0,
    ("B", "caution"):   300.0,
    ("B", "warning"):     0.0,  # B disabled in warning
    ("B", "disabled"):    0.0,
}

BLACK_SWAN_POINTS = 200.0  # max plausible single-bar tail event in DAX
BLACK_SWAN_USD_CAP = 5000.0  # max acceptable USD loss from BSC scenario
MARGIN_CAP_PCT = 0.30  # max 30 % equity used for margin


@dataclass(frozen=True)
class SizingResult:
    lots: float
    risk_usd: float
    capped_by: str  # "standard" | "black_swan_cap" | "margin_cap" | "disabled"
    detail: dict


def compute_lots(
    setup_type: SetupType,
    risk_state: RiskState,
    sl_points: float,
    eur_usd_spot: float,
    *,
    equity_usd: float = 100_000.0,
    dax_price: Optional[float] = None,
    leverage: int = 30,
    lot_step: float = 0.01,
    min_lots: float = 0.01,
) -> SizingResult:
    """Compute final lot size honoring risk_table + BSC + margin cap.

    `dax_price=None` → margin cap deaktivován (vrací inf).
    `lots < min_lots` → SizingResult(lots=0, capped_by="disabled").
    """
    risk_usd = RISK_TABLE.get((setup_type, risk_state))
    if risk_usd is None:
        raise ValueError(f"unknown (setup_type, risk_state): {setup_type, risk_state}")
    if risk_usd <= 0:
        return SizingResult(lots=0.0, risk_usd=0.0, capped_by="disabled",
                            detail={"reason": f"{setup_type}/{risk_state} risk_usd=0"})
    if sl_points <= 0:
        raise ValueError("sl_points must be > 0")
    if eur_usd_spot <= 0:
        raise ValueError("eur_usd_spot must be > 0")

    lots_standard = risk_usd / (sl_points * eur_usd_spot)
    lots_bsc = BLACK_SWAN_USD_CAP / (BLACK_SWAN_POINTS * eur_usd_spot)
    if dax_price is not None and dax_price > 0:
        face_value_per_lot_usd = dax_price * eur_usd_spot  # 1 lot = price EUR face
        margin_per_lot_usd = face_value_per_lot_usd / leverage
        lots_margin = MARGIN_CAP_PCT * equity_usd / margin_per_lot_usd
    else:
        lots_margin = math.inf

    candidates = {
        "standard": lots_standard,
        "black_swan_cap": lots_bsc,
        "margin_cap": lots_margin,
    }
    capped_by = min(candidates, key=candidates.get)
    lots_raw = candidates[capped_by]
    lots_floored = math.floor(lots_raw / lot_step) * lot_step
    if lots_floored < min_lots:
        return SizingResult(lots=0.0, risk_usd=0.0, capped_by="disabled",
                            detail={"reason": "below min_lots",
                                    "candidates": candidates, "raw": lots_raw})
    return SizingResult(
        lots=round(lots_floored, 2),
        risk_usd=risk_usd,
        capped_by=capped_by,
        detail={"candidates": candidates, "raw": lots_raw,
                "lot_step": lot_step, "leverage": leverage,
                "equity_usd": equity_usd, "dax_price": dax_price},
    )


# v3.3.1 — regime-aware sizing wrapper. Re-export for callers that want to
# stay within risk_manager namespace.
def _import_sizing_v331():  # lazy to avoid circular when regime imports risk
    from src.risk.sizing_v331 import calculate_lots_v331
    return calculate_lots_v331


def calculate_lots_v331(*args, **kwargs) -> SizingResult:
    """v3.3.1 wrapper — delegates to src.risk.sizing_v331.calculate_lots_v331.

    Provided here so callers can `from src.risk.risk_manager import calculate_lots_v331`
    without a separate import line. Pavel hybrid plan 2026-04-27 §3.
    """
    return _import_sizing_v331()(*args, **kwargs)


def derive_risk_state(
    cumulative_pnl_usd: float,
    *,
    gap_pct: float = 0.0,
    consecutive_losses: int = 0,
    weekly_pnl_usd: float = 0.0,
    hard_stop_threshold: float = -7000.0,
    warning_threshold: float = -5000.0,
    weekly_pause_threshold: float = -4000.0,
    auto_pause_consecutive: int = 5,
    caution_gap_min: float = 0.005,
    caution_gap_max: float = 0.01,
) -> RiskState:
    """Derive current RiskState from compound DD signals.

    Priority: disabled > warning > caution > normal.
    Returns 'disabled' for L2 hard stop, L3 auto-pause 24h, or L4 weekly pause.
    """
    if cumulative_pnl_usd <= hard_stop_threshold:
        return "disabled"
    if consecutive_losses >= auto_pause_consecutive:
        return "disabled"
    if weekly_pnl_usd <= weekly_pause_threshold:
        return "disabled"
    if cumulative_pnl_usd <= warning_threshold:
        return "warning"
    if caution_gap_min <= abs(gap_pct) <= caution_gap_max:
        return "caution"
    return "normal"
