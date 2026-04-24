"""Trend-following setup — čeká Strategy v3.0 od Architekta.

Placeholder dědí BaseSetup. Konkrétní entry/SL/TP pravidla dodá Architekt.
"""
from .base_setup import BaseSetup, Signal


class TrendSetup(BaseSetup):
    name = "trend"
    setup_type = "A"

    def check_entry(self, market_data):
        return None  # TODO: implement per Strategy v3.0

    def get_sl(self, entry, direction, market_data):
        raise NotImplementedError

    def get_tp(self, entry, sl, direction):
        raise NotImplementedError
