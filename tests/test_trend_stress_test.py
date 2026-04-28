"""Tests pro scripts.trend_stress_test classify() — v3.3.2.1 thresholds."""
from __future__ import annotations

from scripts.trend_stress_test import classify


def _r(scenario, exp):
    return {"scenario": scenario, "expectancy": exp}


class TestClassify:
    def test_pessimistic_below_05_drops(self):
        # v3.3.2.1: pessimistic < +0.5 → DROP
        results = [_r("baseline", 5.0), _r("mild_x1.5", 3.0),
                   _r("pessimistic_x2.0", 0.3), _r("extreme_x3.0", -1.0)]
        v = classify(results)
        assert v["verdict"] == "DROP US-MOM TREND"

    def test_pessimistic_negative_drops(self):
        results = [_r("baseline", 5.0), _r("mild_x1.5", 3.0),
                   _r("pessimistic_x2.0", -0.5), _r("extreme_x3.0", -2.0)]
        v = classify(results)
        assert v["verdict"] == "DROP US-MOM TREND"

    def test_pessimistic_at_threshold_keeps_with_warning(self):
        results = [_r("baseline", 5.0), _r("mild_x1.5", 3.0),
                   _r("pessimistic_x2.0", 0.6), _r("extreme_x3.0", -1.0)]
        v = classify(results)
        # 0.6 > 0.5 (drop threshold) → KEEP (with warning since within +1 band)
        assert "KEEP" in v["verdict"]

    def test_strong_baseline_keeps(self):
        results = [_r("baseline", 5.0), _r("mild_x1.5", 3.0),
                   _r("pessimistic_x2.0", 2.0), _r("extreme_x3.0", -0.5)]
        v = classify(results)
        assert "KEEP" in v["verdict"]

    def test_threshold_constants_v3321(self):
        from scripts.trend_stress_test import (
            THRESHOLD_PESSIMISTIC, THRESHOLD_MILD, THRESHOLD_BASELINE,
        )
        assert THRESHOLD_PESSIMISTIC == 0.5     # UPDATED v3.3.2.1
        assert THRESHOLD_MILD == 1.5
        assert THRESHOLD_BASELINE == 3.3
