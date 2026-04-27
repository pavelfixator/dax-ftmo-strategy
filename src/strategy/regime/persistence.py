"""Regime persistence layer — asymetric switching rule.

Rules (Strategy v3.3.1 §2.2):
  - Switch TO CRASH:    INSTANT (panic protection — 1 day signal sufficient)
  - Switch FROM CRASH:  2 consecutive non-CRASH days required
  - Other switches (TREND ↔ CALM ↔ UNDEFINED): 2-day consensus required

Účel: zabránit rychlému flipu mezi regimy přes 1-day noise, ale udržet
rychlou reakci na crash signál (downside protection).

Spec: Strategy v3.3.1 §2.2.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .classifier import Regime


def get_active_regime(history: Sequence[Regime],
                      raw_today: Regime,
                      *, current_active: Optional[Regime] = None) -> Regime:
    """Vrátí "active" regime po aplikaci asymmetric persistence rule.

    Logic:
      1. raw_today == CRASH → CRASH (instant switch).
      2. current_active == CRASH:
         exit požaduje 2 consecutive non-CRASH days
         (yesterday raw + raw_today oba non-CRASH); jinak zůstaň CRASH.
      3. current_active != CRASH (or None — cold start):
         non-CRASH → non-CRASH switch požaduje 2-day consensus
         (yesterday raw == raw_today AND raw_today != current_active).
         Cold start (current_active is None) → vrať raw_today přímo.

    Args:
        history: sequence raw daily regimes (chronological, latest last).
                 Použije se history[-1] = včerejší raw klasifikace.
        raw_today: dnešní raw klasifikace z classify_regime_raw().
        current_active: aktuální "active" regime z předchozího dne (post-rule).
                        None pro cold start.

    Returns:
        Regime — režim pro dnešní obchodování.
    """
    # Rule 1: panic protection — instant switch to CRASH
    if raw_today == Regime.CRASH:
        return Regime.CRASH

    # Cold start: no prior active state → trust raw_today (best estimate)
    if current_active is None:
        return raw_today

    yesterday_raw: Optional[Regime] = history[-1] if history else None

    # Rule 2: exit from CRASH requires 2 consecutive non-CRASH days
    if current_active == Regime.CRASH:
        # raw_today is already non-CRASH (handled by Rule 1 above)
        if yesterday_raw is not None and yesterday_raw != Regime.CRASH:
            return raw_today  # both non-CRASH → exit
        return Regime.CRASH  # only 1 non-CRASH day → stay

    # Rule 3: non-CRASH → non-CRASH switch needs 2-day consensus
    if raw_today == current_active:
        return current_active  # no change needed
    if yesterday_raw == raw_today:
        return raw_today  # 2-day consensus → switch
    return current_active  # only 1-day signal → stay
