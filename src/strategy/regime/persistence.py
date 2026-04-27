"""Regime persistence layer — asymetric switching rule.

Rules (Strategy v3.3.1 §2.2):
  - Switch TO CRASH:    INSTANT (panic protection — 1 day signal sufficient)
  - Switch FROM CRASH:  2 consecutive non-CRASH days required
  - Other switches (TREND ↔ CALM ↔ UNDEFINED): 2-day consensus required

Účel: zabránit rychlému flipu mezi regimy přes 1-day noise, ale udržet
rychlou reakci na crash signál (downside protection).

Implementace stub. Plná logika v Sekci 2.

Spec: Strategy v3.3.1 §2.2.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional, Sequence

from .classifier import Regime


def get_active_regime(history: Sequence[Regime],
                      raw_today: Regime,
                      *, current_active: Optional[Regime] = None) -> Regime:
    """Vrátí "active" regime po aplikaci asymmetric persistence rule.

    Stub. Plná implementace v Sekci 2:
      1. Pokud raw_today == CRASH → return CRASH (instant switch).
      2. Pokud current_active == CRASH a (raw_today, history[-1]) jsou oba
         non-CRASH → switch FROM crash na raw_today.
      3. Jinak vyžaduj 2-day consensus na novém regime před switch.

    Args:
        history: Sequence raw daily regimes (chronological, latest last).
                 Typicky posledních N=5 dní pro safety margin.
        raw_today: dnešní raw klasifikace z classify_regime_raw().
        current_active: aktuální "active" regime (z předchozího dne, post-rule).
                        None na začátku (cold start).

    Returns:
        Regime — režim, který se má použít pro dnešní obchodování.

    Raises:
        NotImplementedError: dokud Sekce 2 nedokončí.
    """
    raise NotImplementedError(
        "get_active_regime: full implementation deferred to Sekce 2"
    )
