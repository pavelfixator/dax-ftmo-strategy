"""Regime classification layer pro Strategy v3.3.1.

Veřejné API:
  - Regime: enum se 4 hodnotami (TREND, CALM, CRASH, UNDEFINED)
  - RegimeSignals: dataclass s 3 raw signály (atr_pct, adx_h4, ema50_slope)
  - classify_regime_raw: konsenzus 2/3 signály → Regime
  - get_active_regime: persistence rule wrapper (asymmetric switch)

Plné implementace dorazí v Sekci 2 — toto je skeleton (NotImplementedError).

Spec: Strategy v3.3.1 §2.1-2.2 (Regime Classifier + Persistence Rule).
"""
from .classifier import (  # noqa: F401
    Regime, RegimeSignals, classify_regime_raw,
)
from .persistence import get_active_regime  # noqa: F401
