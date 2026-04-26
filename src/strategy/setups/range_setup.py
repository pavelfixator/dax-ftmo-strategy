"""Range / mean-reversion setup — čeká Strategy v3.0 od Architekta."""
from .base_setup import BaseSetup, Signal


class RangeSetup(BaseSetup):
    name = "range"
    setup_type = "B"

    def check_entry(self, market_data):
        return None  # TODO: implement per Strategy v3.0

    def get_sl(self, entry, direction, market_data):
        raise NotImplementedError

    def get_tp(self, entry, sl, direction):
        raise NotImplementedError
