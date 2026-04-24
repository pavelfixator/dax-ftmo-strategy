"""Abstract base class pro všechny setupy.

Spec: Blok 3 ÚKOL 7.1 (setups/base_setup.py).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Signal:
    setup_name: str
    direction: str  # "LONG" or "SHORT"
    entry: float
    sl: float
    tp: float
    lots: float
    risk_usd: float
    confidence: float  # 0..1
    filters_met: int
    filters_total: int

    @property
    def rrr(self) -> float:
        reward = abs(self.tp - self.entry)
        risk = abs(self.entry - self.sl)
        return reward / risk if risk else 0.0


class BaseSetup(ABC):
    name: str = "base"
    setup_type: str = "A"  # "A" nebo "B"

    @abstractmethod
    def check_entry(self, market_data) -> Optional[Signal]:
        """Vrátí Signal pokud jsou splněny všechny filtry, jinak None."""

    @abstractmethod
    def get_sl(self, entry: float, direction: str, market_data) -> float:
        """Spočítá SL pro daný entry a směr."""

    @abstractmethod
    def get_tp(self, entry: float, sl: float, direction: str) -> float:
        """Spočítá TP pro daný entry + SL + směr (min RRR 1:2)."""
